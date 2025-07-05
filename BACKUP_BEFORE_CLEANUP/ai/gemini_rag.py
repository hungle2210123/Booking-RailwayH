"""
🧠 Gemini-Enhanced RAG System for Hotel Operations
Advanced AI-powered question answering with Google Gemini API
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from .simple_rag import SimpleHotelRAG

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiEnhancedRAG:
    """
    Advanced RAG system powered by Google Gemini API
    Combines vector search with LLM reasoning for superior responses
    """
    
    def __init__(self, google_api_key: str = None):
        """Initialize Gemini-enhanced RAG system"""
        
        # Initialize base RAG system
        self.simple_rag = SimpleHotelRAG()
        
        # Initialize Gemini API
        self.api_key = google_api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            logger.warning("⚠️ No Gemini API key found. Using simple RAG fallback.")
            self.gemini_available = False
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
                self.gemini_available = True
                logger.info("✅ Gemini API initialized successfully")
            except ImportError:
                logger.warning("⚠️ Gemini library not available. Using simple RAG fallback.")
                self.gemini_available = False
        
        # Conversation history for multi-turn chats
        self.conversation_history = {}
        
        logger.info("✅ Gemini-Enhanced RAG System initialized")
    
    def generate_enhanced_response(self, query: str, guest_name: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """
        Generate enhanced response using Gemini + RAG
        Falls back to simple RAG if Gemini unavailable
        """
        
        try:
            # Step 1: Retrieve relevant context using existing RAG
            logger.info(f"🔍 Retrieving context for: '{query}'")
            rag_context = self.simple_rag.retrieve_context(query, guest_name)
            
            # Step 2: Get guest booking context if available
            guest_context = {}
            if guest_name:
                guest_context = self._get_enhanced_guest_context(guest_name)
            
            # Step 3: Use Gemini for intelligent response generation
            if self.gemini_available:
                enhanced_response = self._generate_gemini_response(
                    query, rag_context, guest_context, conversation_id
                )
            else:
                # Fallback to simple RAG
                logger.info("Using simple RAG fallback")
                enhanced_response = self.simple_rag.generate_rag_response(query, guest_name)
                enhanced_response['gemini_enhanced'] = False
                
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Error in enhanced response generation: {e}")
            # Always fallback to simple RAG on error
            fallback_response = self.simple_rag.generate_rag_response(query, guest_name)
            fallback_response['gemini_enhanced'] = False
            fallback_response['error'] = str(e)
            return fallback_response
    
    def _generate_gemini_response(self, query: str, rag_context: Dict, guest_context: Dict, conversation_id: str = None) -> Dict[str, Any]:
        """Generate response using Gemini API with RAG context"""
        
        try:
            # Build comprehensive prompt
            prompt = self._build_gemini_prompt(query, rag_context, guest_context, conversation_id)
            
            # Generate response with Gemini
            response = self.model.generate_content(prompt)
            
            if response.text:
                # Parse Gemini response
                parsed_response = self._parse_gemini_response(response.text, rag_context)
                
                # Update conversation history
                if conversation_id:
                    self._update_conversation_history(conversation_id, query, parsed_response['answer'])
                
                # Add metadata
                parsed_response.update({
                    'gemini_enhanced': True,
                    'model_used': 'gemini-2.5-flash-preview-05-20',
                    'timestamp': datetime.now().isoformat(),
                    'confidence': min(rag_context.get('confidence', 0.8) + 0.2, 1.0),  # Boost confidence with Gemini
                    'sources': [entry['topic'] for entry in rag_context.get('relevant_info', [])],
                    'guest_personalized': bool(guest_context),
                    'conversation_id': conversation_id
                })
                
                return parsed_response
            else:
                raise Exception("Empty response from Gemini")
                
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            # Fallback to simple RAG
            fallback = self.simple_rag.generate_rag_response(query)
            fallback['gemini_enhanced'] = False
            fallback['fallback_reason'] = str(e)
            return fallback
    
    def _build_gemini_prompt(self, query: str, rag_context: Dict, guest_context: Dict, conversation_id: str = None) -> str:
        """Build comprehensive prompt for Gemini API"""
        
        # Get conversation history
        conversation_history = self.conversation_history.get(conversation_id, []) if conversation_id else []
        
        # Build hotel knowledge context
        knowledge_context = ""
        if rag_context.get('relevant_info'):
            knowledge_context = "\n".join([
                f"- {entry['topic']}: {entry['content']}"
                for entry in rag_context['relevant_info'][:5]
            ])
        
        # Build guest context
        guest_info = ""
        if guest_context:
            guest_info = f"""
GUEST INFORMATION:
- Name: {guest_context.get('name', 'N/A')}
- Booking Status: {guest_context.get('status', 'N/A')}
- Check-in: {guest_context.get('checkin_date', 'N/A')}
- Check-out: {guest_context.get('checkout_date', 'N/A')}
- VIP Status: {'Yes' if guest_context.get('vip_status') else 'No'}
- Previous Bookings: {guest_context.get('booking_count', 0)}
"""
        
        # Build conversation context
        conversation_context = ""
        if conversation_history:
            conversation_context = "\nPREVIOUS CONVERSATION:\n" + "\n".join([
                f"Guest: {item['query']}\nAssistant: {item['response'][:200]}..."
                for item in conversation_history[-3:]  # Last 3 exchanges
            ])
        
        prompt = f"""You are an expert AI assistant for 118 Hang Bac Hostel in Hanoi's Old Quarter. 

HOTEL KNOWLEDGE BASE:
{knowledge_context}

{guest_info}

{conversation_context}

GUEST QUERY: "{query}"

INSTRUCTIONS:
1. Provide a helpful, accurate response based on the hotel knowledge
2. Use the guest's name if available and personalize the response
3. Consider the conversation history for context
4. Be concise but comprehensive
5. Include specific details (times, prices, locations) when relevant
6. Suggest next steps or related services when appropriate
7. Maintain a friendly, professional hotel reception tone
8. If information is missing, clearly state what you don't know

RESPONSE FORMAT:
Provide a natural, conversational response as if you're a knowledgeable hotel receptionist. Include:
- Direct answer to the query
- Relevant additional information
- Helpful suggestions or next steps

Do not include any JSON formatting or metadata in your response - just the natural conversation text.
"""
        
        return prompt
    
    def _parse_gemini_response(self, gemini_text: str, rag_context: Dict) -> Dict[str, Any]:
        """Parse and structure Gemini response"""
        
        # Extract answer (Gemini response is already formatted)
        answer = gemini_text.strip()
        
        # Generate suggestions based on the query and context
        suggestions = self._generate_intelligent_suggestions(answer, rag_context)
        
        return {
            'query': rag_context.get('query', ''),
            'answer': answer,
            'suggestions': suggestions,
            'reasoning_type': 'gemini_enhanced',
            'context_used': len(rag_context.get('relevant_info', []))
        }
    
    def _generate_intelligent_suggestions(self, answer: str, rag_context: Dict) -> List[str]:
        """Generate intelligent follow-up suggestions"""
        
        suggestions = []
        answer_lower = answer.lower()
        
        # Context-aware suggestions based on response content
        if 'check-in' in answer_lower:
            suggestions.extend([
                "Need help with early check-in arrangements?",
                "Would you like information about luggage storage?",
                "Ask about airport transportation options"
            ])
        
        elif 'food' in answer_lower or 'restaurant' in answer_lower:
            suggestions.extend([
                "Need specific dietary requirements accommodated?",
                "Want recommendations for different cuisines?",
                "Ask about food delivery options"
            ])
        
        elif 'taxi' in answer_lower or 'transport' in answer_lower:
            suggestions.extend([
                "Need help booking the taxi service?",
                "Want information about public transport?",
                "Ask about Grab taxi app setup"
            ])
        
        elif 'wifi' in answer_lower:
            suggestions.extend([
                "Having trouble connecting to WiFi?",
                "Need technical support for devices?",
                "Ask about internet speed for work"
            ])
        
        # Add general helpful suggestions
        suggestions.extend([
            "Any other questions about hotel services?",
            "Need information about local attractions?",
            "Would you like our WhatsApp contact for quick assistance?"
        ])
        
        return suggestions[:3]  # Return top 3 most relevant
    
    def _get_enhanced_guest_context(self, guest_name: str) -> Dict[str, Any]:
        """Get enhanced guest context with intelligent analysis"""
        
        try:
            # Use the existing guest context from simple RAG
            basic_context = self.simple_rag._get_guest_context(guest_name)
            
            # Enhanced context would include:
            # - Booking status analysis
            # - Preference learning
            # - Service history
            # - Cultural background detection
            
            # For now, return the basic context
            # This can be enhanced with more sophisticated guest profiling
            
            return basic_context
            
        except Exception as e:
            logger.error(f"Error getting enhanced guest context: {e}")
            return {}
    
    def _update_conversation_history(self, conversation_id: str, query: str, response: str):
        """Update conversation history for multi-turn chat"""
        
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []
        
        self.conversation_history[conversation_id].append({
            'query': query,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 10 exchanges to manage memory
        if len(self.conversation_history[conversation_id]) > 10:
            self.conversation_history[conversation_id] = self.conversation_history[conversation_id][-10:]
    
    def start_conversation(self, guest_name: str = None) -> str:
        """Start a new conversation and return conversation ID"""
        
        conversation_id = f"conv_{datetime.now().timestamp()}_{guest_name or 'guest'}"
        self.conversation_history[conversation_id] = []
        
        return conversation_id
    
    def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get summary of conversation for analysis"""
        
        if conversation_id not in self.conversation_history:
            return {}
        
        history = self.conversation_history[conversation_id]
        
        return {
            'conversation_id': conversation_id,
            'exchange_count': len(history),
            'duration_minutes': (
                datetime.fromisoformat(history[-1]['timestamp']) - 
                datetime.fromisoformat(history[0]['timestamp'])
            ).total_seconds() / 60 if len(history) > 1 else 0,
            'topics_discussed': self._extract_topics(history),
            'last_query': history[-1]['query'] if history else None
        }
    
    def _extract_topics(self, history: List[Dict]) -> List[str]:
        """Extract main topics discussed in conversation"""
        
        topics = set()
        
        for exchange in history:
            query = exchange['query'].lower()
            
            if any(word in query for word in ['check-in', 'check in', 'arrival']):
                topics.add('check-in')
            if any(word in query for word in ['check-out', 'checkout', 'departure']):
                topics.add('check-out')
            if any(word in query for word in ['food', 'eat', 'restaurant', 'hungry']):
                topics.add('dining')
            if any(word in query for word in ['taxi', 'transport', 'airport']):
                topics.add('transportation')
            if any(word in query for word in ['wifi', 'internet']):
                topics.add('wifi')
            if any(word in query for word in ['attraction', 'visit', 'tourism']):
                topics.add('tourism')
        
        return list(topics)

# Global instance
gemini_rag = None

def initialize_gemini_rag(api_key: str = None):
    """Initialize global Gemini RAG instance"""
    global gemini_rag
    gemini_rag = GeminiEnhancedRAG(api_key)
    return gemini_rag

def get_gemini_rag():
    """Get global Gemini RAG instance"""
    return gemini_rag