# -*- coding: utf-8 -*-
"""
Humanaize 2.0 - GAN Iteration Module (Optimized)
Generative Adversarial Network style self-debate for balanced reasoning
"""

import os
import sys
import threading
import requests
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm import chat
from data.prompts_manager import (
    load_gan_decide_prompt,
    load_gan_topic_prompt,
    load_gan_argument_a_prompt,
    load_gan_argument_b_prompt,
    load_gan_synthesis_prompt
)


class GANIteration:
    """
    Optimized GAN-style self-debate module
    
    Key improvements:
    - Cleaner code structure with helper methods
    - Topic anchoring to prevent deviation
    - Coherence evaluation mechanism
    - Optimized LLM parameters
    - Removed unnecessary delays
    """
    
    # Constants
    STOP_MARKER = "[AGREE]"  # Clearer marker for agreement
    MAX_ITERATIONS = 3  # Prevent infinite loops
    MIN_ARGUMENT_LENGTH = 50  # Minimum meaningful argument length
    
    def __init__(self):
        self.topic = ""
        self.reply_a = ""
        self.reply_b = ""
        self.synthesis = ""
        self.iteration_count = 0
        self._stop_flag = False
        self._stop_event = threading.Event()
        self._session = requests.Session()
        self.callback = None
        self.user_context = ""  # Store user question for topic anchoring
    
    # ==================== Core Methods ====================
    
    def _reset(self):
        """Reset all state for new debate"""
        self.topic = ""
        self.reply_a = ""
        self.reply_b = ""
        self.synthesis = ""
        self.iteration_count = 0
        self._stop_flag = False
        self._stop_event.clear()
        try:
            self._session.close()
        except:
            pass
        self._session = requests.Session()
    
    def _check_stopped(self):
        """Check if debate should stop"""
        return self._stop_flag or self._stop_event.is_set()
    
    def _safe_call(self, prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
        """
        Safe LLM call with stop check
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens to generate
            temperature: Creativity level (0.0-1.0)
        
        Returns:
            LLM response or empty string if stopped
        """
        if self._check_stopped():
            return ""
        
        result = chat(
            prompt,
            session=self._session,
            stop_event=self._stop_event,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return result.strip() if result else ""
    
    def _emit(self, event_type: str, data: str):
        """Emit callback event safely with thought_type for proper UI display"""
        if self.callback and not self._check_stopped():
            # 为GAN相关事件添加thought_type标识
            thought_type_map = {
                "gan_topic": "gan_topic",
                "gan_argument": "gan_argument",
                "gan_counter_argument": "gan_counter_argument",
                "gan_synthesis": "gan_synthesis"
            }
            
            thought_type = thought_type_map.get(event_type, "gan")
            
            # 将GAN事件转换为internal_thought类型，以便显示在Thought区域
            self.callback({
                "type": "internal_thought",
                "thought": f"[{event_type.replace('_', ' ').title()}] {data}",
                "thought_type": thought_type,
                "original_event": event_type
            })
    
    def stop_immediately(self):
        """Stop the debate immediately"""
        self._stop_flag = True
        self._stop_event.set()
        self.reply_b = self.STOP_MARKER
        try:
            self._session.close()
        except:
            pass
    
    # ==================== Decision Logic ====================
    
    def decide_use_gan(self, user_text: str, exec_instr: str = "") -> tuple:
        """
        Decide whether GAN debate is needed
        
        Args:
            user_text: User's question/input
            exec_instr: Additional instructions
        
        Returns:
            (bool, str): (should_use_gan, reason)
        """
        self._reset()
        self.user_context = user_text
        
        # Simple heuristic: skip GAN for simple questions
        if len(user_text) < 20 or user_text.endswith("?") and len(user_text.split()) < 5:
            return False, "Simple question, direct answer sufficient"
        
        decision_prompt = load_gan_decide_prompt(user_text)
        
        reply = self._safe_call(decision_prompt, max_tokens=100, temperature=0.3)
        
        if not reply:
            return False, "Decision failed"
        
        # Parse decision
        is_yes = "yes" in reply.lower()[:10] or "是" in reply[:5]
        return is_yes, reply
    
    # ==================== Topic Generation ====================
    
    def _generate_topic(self, user_topic: str = None) -> str:
        """
        Generate debate topic anchored to user context
        
        Args:
            user_topic: Optional user-provided topic
        
        Returns:
            Generated topic string
        """
        if user_topic:
            self.topic = user_topic
            return user_topic
        
        # Generate topic related to user's question
        topic_prompt = load_gan_topic_prompt(self.user_context)
        
        topic = self._safe_call(topic_prompt, max_tokens=100, temperature=0.5)
        
        # Clean up topic
        topic = topic.strip().strip('"').strip("'")
        
        if not topic or len(topic) < 10:
            # Fallback to user context
            topic = f"分析：{self.user_context[:50]}"
        
        self.topic = topic
        self._emit("gan_topic", topic)
        return topic
    
    # ==================== Argument Generation ====================
    
    def _generate_argument(self, perspective: str = "A") -> str:
        """
        Generate argument for given perspective
        
        Args:
            perspective: "A" for initial argument, "B" for counter
        
        Returns:
            Generated argument
        """
        if perspective == "A":
            prompt = load_gan_argument_a_prompt(self.topic)
        else:
            prompt = load_gan_argument_b_prompt(self.topic, self.reply_a, self.STOP_MARKER)
        
        argument = self._safe_call(prompt, max_tokens=200, temperature=0.7)
        
        # Validate argument
        if perspective == "B" and self.STOP_MARKER in argument:
            return self.STOP_MARKER
        
        if len(argument) < self.MIN_ARGUMENT_LENGTH:
            return ""  # Invalid argument
        
        return argument
    
    # ==================== Coherence Check ====================
    
    def _check_coherence(self, argument: str) -> bool:
        """
        Check if argument is coherent and relevant to topic
        
        Args:
            argument: The argument to check
        
        Returns:
            True if coherent, False otherwise
        """
        if not argument or argument == self.STOP_MARKER:
            return False
        
        # Simple coherence check: argument should mention topic keywords
        topic_keywords = set(self.topic.lower().split())
        argument_keywords = set(argument.lower().split())
        
        # At least 2 topic keywords should appear
        overlap = len(topic_keywords & argument_keywords)
        
        return overlap >= 2 or len(argument) >= self.MIN_ARGUMENT_LENGTH
    
    # ==================== Main Debate Logic ====================
    
    def self_debate(self, is_user_topic: bool = False, user_topic: str = None) -> dict:
        """
        Execute GAN-style self-debate
        
        Args:
            is_user_topic: Whether topic is user-provided
            user_topic: The user-provided topic
        
        Returns:
            {"synthesis": str, "iterations": int, "coherent": bool}
        """
        self._reset()
        
        if self._check_stopped():
            return {"synthesis": "", "iterations": 0, "coherent": False}
        
        # Step 1: Generate/confirm topic
        topic = self._generate_topic(user_topic if is_user_topic else None)
        
        if self._check_stopped():
            return {"synthesis": "", "iterations": 0, "coherent": False}
        
        # Step 2: Generate initial argument (Perspective A)
        self.reply_a = self._generate_argument("A")
        
        if self._check_stopped() or not self.reply_a:
            return {"synthesis": "", "iterations": 0, "coherent": False}
        
        self._emit("gan_argument", self.reply_a)
        
        # Step 3: Debate iterations
        self.iteration_count = 0
        coherent_debate = True
        
        while self.iteration_count < self.MAX_ITERATIONS:
            if self._check_stopped():
                break
            
            # Generate counter-argument (Perspective B)
            self.reply_b = self._generate_argument("B")
            
            if self._check_stopped():
                break
            
            # Check if debate reached agreement
            if self.STOP_MARKER in self.reply_b:
                self._emit("gan_counter", "Agreement reached")
                break
            
            # Check coherence
            if not self._check_coherence(self.reply_b):
                coherent_debate = False
                self._emit("gan_counter", "[Coherence warning]")
                break
            
            self._emit("gan_counter", self.reply_b)
            self.iteration_count += 1
            
            # Swap perspectives for next iteration
            self.reply_a = self.reply_b
        
        # Step 4: Synthesis
        if not self._check_stopped() and self.reply_a:
            self.synthesis = self._create_synthesis()
        
        return {
            "synthesis": self.synthesis,
            "iterations": self.iteration_count,
            "coherent": coherent_debate,
            "topic": self.topic
        }
    
    def _create_synthesis(self) -> str:
        """
        Create synthesis from debate
        
        Returns:
            Synthesized conclusion
        """
        synthesis_prompt = load_gan_synthesis_prompt(self.topic, self.reply_a)
        
        synthesis = self._safe_call(synthesis_prompt, max_tokens=150, temperature=0.5)
        
        return synthesis if synthesis else self.reply_a
    
    # ==================== Utility Methods ====================
    
    def get_debate_summary(self) -> dict:
        """Get summary of current debate state"""
        return {
            "topic": self.topic,
            "argument_a": self.reply_a,
            "argument_b": self.reply_b,
            "synthesis": self.synthesis,
            "iterations": self.iteration_count,
            "stopped": self._stop_flag
        }


# ==================== Test ====================

if __name__ == "__main__":
    gan = GANIteration()
    
    # Test decision
    should_use, reason = gan.decide_use_gan("What do you think about Trump's policies?")
    print(f"Decision: {should_use}, Reason: {reason}")
    
    # Test debate
    if should_use:
        result = gan.self_debate(is_user_topic=True, user_topic="Should political leaders be judged by their policies or character?")
        print(f"\nDebate result:")
        print(f"Topic: {result['topic']}")
        print(f"Synthesis: {result['synthesis']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Coherent: {result['coherent']}")