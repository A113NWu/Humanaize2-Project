#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心模組初始化
"""

from .personality import load_personality, save_personality, get_personality_context, get_personality_description, should_speak_actively
from .autonomous import check_silence_and_decide