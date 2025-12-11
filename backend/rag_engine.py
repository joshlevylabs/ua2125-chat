"""
RAG (Retrieval-Augmented Generation) Engine
Handles document retrieval and answer generation
"""
import logging
from typing import List, Dict, Tuple
from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    SYSTEM_PROMPT,
    CHAT_TEMPERATURE,
    MAX_TOKENS,
    TOP_K_RESULTS
)
# Use database-backed embeddings index instead of file-based
from db_embeddings_index import db_embeddings_index
from models import ChatMessage, Source

logger = logging.getLogger(__name__)


class RAGEngine:
    """Retrieval-Augmented Generation engine for chatbot"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.embeddings_index = db_embeddings_index  # PostgreSQL-backed storage

    def retrieve_context(self, query: str, top_k: int = TOP_K_RESULTS) -> Tuple[str, List[Source]]:
        """
        Retrieve relevant context from knowledge base

        Args:
            query: User's question
            top_k: Number of top results to retrieve

        Returns:
            Tuple of (formatted_context, sources_list)
        """
        # Search for relevant documents
        search_results = self.embeddings_index.search(query, top_k=top_k)

        if not search_results:
            return "No relevant information found in the knowledge base.", []

        # Format context for LLM
        context_parts = []
        sources = []

        for i, (metadata, similarity) in enumerate(search_results, 1):
            content = metadata.get('content', '')
            source = metadata.get('source', 'Unknown')
            chunk_id = metadata.get('chunk_id', '')

            context_parts.append(f"[Source {i}: {source}]\n{content}\n")

            sources.append(Source(
                content=content[:300] + "..." if len(content) > 300 else content,
                source=source,
                similarity=round(similarity, 3)
            ))

        formatted_context = "\n".join(context_parts)
        logger.info(f"Retrieved {len(sources)} relevant sources")

        return formatted_context, sources

    def detect_troubleshooting(self, message: str, conversation_history: List[ChatMessage] = None) -> bool:
        """
        Detect if the user is describing a problem or issue

        Args:
            message: User's message
            conversation_history: Previous conversation

        Returns:
            True if troubleshooting mode should be activated
        """
        # Keywords that indicate troubleshooting
        problem_keywords = [
            'not working', 'no sound', 'no audio', 'issue', 'problem', 'error',
            'broken', 'failed', 'failing', 'doesn\'t work', 'won\'t work',
            'can\'t', 'cannot', 'unable', 'trouble', 'help', 'fix',
            'not responding', 'no output', 'distorted', 'noise', 'buzzing',
            'crackling', 'intermittent', 'cutting out', 'dropping',
            'not connecting', 'won\'t connect', 'no connection'
        ]

        message_lower = message.lower()

        # Check if message contains problem indicators
        for keyword in problem_keywords:
            if keyword in message_lower:
                return True

        # Check conversation history for troubleshooting context
        if conversation_history:
            # Look at last 2 assistant messages to see if we're already troubleshooting
            recent_assistant_msgs = [msg for msg in conversation_history[-4:] if msg.role == "assistant"]
            for msg in recent_assistant_msgs:
                if "firmware version" in msg.content.lower() or "input source" in msg.content.lower():
                    return True  # We're in diagnostic mode

        return False

    def generate_response(
        self,
        user_message: str,
        context: str,
        conversation_history: List[ChatMessage] = None
    ) -> str:
        """
        Generate response using OpenAI API with retrieved context

        Args:
            user_message: User's current message
            context: Retrieved context from knowledge base
            conversation_history: Previous conversation messages

        Returns:
            Generated response text
        """
        # Build messages for OpenAI API
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Add conversation history (last 5 messages for context)
        if conversation_history:
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Detect if this is a troubleshooting scenario
        is_troubleshooting = self.detect_troubleshooting(user_message, conversation_history)

        # Check if this is a configuration-dependent question
        import re
        config_patterns = [
            r'both.*(playing|active|inputs)',
            r'(default|primary).*(secondary|analog)',
            r'(secondary|analog).*(default|primary)',
            r'two inputs',
            r'multiple inputs',
            r'hdmi.*(and|&|\+).*analog',
            r'analog.*(and|&|\+).*hdmi'
        ]
        needs_config_info = any(re.search(pattern, user_message.lower()) for pattern in config_patterns)

        # Build user prompt based on context
        if is_troubleshooting:
            # Check if we already have diagnostic info from conversation history
            has_diagnostic_info = False
            if conversation_history and len(conversation_history) >= 2:
                # Look for diagnostic answers in recent messages
                recent_user_msgs = [msg.content.lower() for msg in conversation_history[-3:] if msg.role == "user"]
                diagnostic_indicators = ['firmware', 'version', 'input', 'source', 'sonarc', 'connected', 'settings']
                has_diagnostic_info = any(indicator in ' '.join(recent_user_msgs) for indicator in diagnostic_indicators)

            if not has_diagnostic_info:
                user_prompt = f"""The user is reporting an issue with their UA2-125 amplifier.

**User's Issue:**
{user_message}

**CRITICAL INSTRUCTION - YOU MUST ASK QUESTIONS FIRST:**
DO NOT provide troubleshooting steps yet. First, you MUST gather diagnostic information by asking the user these questions:

**Please ask the user to provide:**
1. What firmware version is installed on the amplifier? (Check in SonArc app)
2. What input source are they using? (e.g., Control4, Crestron, HDMI ARC, optical, analog)
3. What are the current SonArc app settings? (input selection, zone configuration, volume settings)
4. How are the speakers and input sources connected?
5. When does the issue occur? (during specific conditions, randomly, after updates, etc.)

**Your Response Format:**
- Start with empathy: "I understand you're experiencing [issue]. Let me help diagnose this."
- Ask 3-4 of the essential diagnostic questions above
- End with: "Once you provide this information, I'll be able to give you targeted troubleshooting steps."

**Context for reference only (don't use yet):**
{context}"""
            else:
                user_prompt = f"""The user has provided diagnostic information about their UA2-125 issue. Now provide targeted troubleshooting steps.

**Context from Documentation:**
{context}

**User's Issue and Setup:**
{user_message}

**Conversation History Contains:**
Their previous responses with diagnostic details (firmware, input source, settings, etc.)

**Instructions:**
- Review the conversation history to understand their specific setup
- Provide targeted troubleshooting steps based on their exact configuration
- Reference relevant troubleshooting documentation from the context
- Use step-by-step format with clear actions
- Include verification steps
- Be solution-focused and specific to their setup"""
        elif needs_config_info:
            # Check if crossover mode is mentioned in the conversation
            has_crossover_mode = False
            if conversation_history:
                recent_msgs = ' '.join([msg.content.lower() for msg in conversation_history[-3:]])
                has_crossover_mode = any(mode in recent_msgs for mode in ['mute', 'duck', 'mix', 'mixed'])

            if not has_crossover_mode and not any(mode in user_message.lower() for mode in ['mute', 'duck', 'mix', 'mixed']):
                user_prompt = f"""The user is asking about behavior when multiple inputs are active on the UA2-125 amplifier.

**User's Question:**
{user_message}

**CRITICAL - MISSING CONFIGURATION INFORMATION:**
The answer to this question depends on the **Crossover Behavior** setting (MUTE, DUCK, or MIX mode). The user has NOT specified which mode is configured.

**Your Response MUST:**
1. Explain that the behavior depends on the Crossover Behavior setting
2. Briefly describe each mode:
   - **MUTE mode**: Secondary input completely overrides default input (default is muted)
   - **DUCK mode**: Secondary input is dominant, default input is attenuated by -20dB
   - **MIX mode**: Both inputs are mixed together
3. Ask the user: "Which Crossover Behavior mode do you have configured in the SonArc app (MUTE, DUCK, or MIX)?"
4. DO NOT provide a specific answer until they specify the mode

**Context for reference (but DON'T answer yet):**
{context}"""
            else:
                user_prompt = f"""Based on the following context from the UA2-125 documentation, please answer the user's question about multi-input behavior.

**Context from I/O Truth Table:**
{context}

**User Question:**
{user_message}

**Instructions:**
- The user has specified or the conversation contains information about the crossover mode (MUTE, DUCK, or MIX)
- Provide the EXACT behavior from the I/O Truth Table for that specific mode
- For MUTE mode: Secondary input overrides (default is completely muted)
- For DUCK mode: Secondary input is heard clearly, default is attenuated by -20dB
- For MIX mode: Both inputs are mixed together
- Include LED color information from the truth table
- Be specific and accurate - do not improvise"""
        else:
            user_prompt = f"""Based on the following context from the UA2-125 documentation, please answer the user's question.

**Context:**
{context}

**User Question:**
{user_message}

**Instructions:**
- Answer based ONLY on the provided context
- If the context doesn't contain the answer, say so clearly
- Use structured formatting (bullet points, numbered steps, tables) when appropriate
- Include relevant specifications when helpful
- Be concise but thorough"""

        messages.append({
            "role": "user",
            "content": user_prompt
        })

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=CHAT_TEMPERATURE,
                max_tokens=MAX_TOKENS
            )

            answer = response.choices[0].message.content
            logger.info(f"Generated response successfully (troubleshooting={is_troubleshooting})")
            return answer

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error generating a response. Please try again."

    def chat(
        self,
        user_message: str,
        conversation_history: List[ChatMessage] = None
    ) -> Tuple[str, List[Source]]:
        """
        Main chat interface: retrieve + generate

        Args:
            user_message: User's message
            conversation_history: Previous conversation

        Returns:
            Tuple of (response_text, sources_used)
        """
        logger.info(f"Processing chat message: {user_message[:100]}...")

        # Step 1: Retrieve relevant context
        context, sources = self.retrieve_context(user_message)

        # Step 2: Generate response
        response = self.generate_response(
            user_message=user_message,
            context=context,
            conversation_history=conversation_history or []
        )

        return response, sources


# Global instance
rag_engine = RAGEngine()
