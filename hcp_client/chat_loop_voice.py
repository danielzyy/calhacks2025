# chat_loop_voice.py
"""
Press-spacebar voice chat loop (stable TTS version)
Requires:
    pip install pyttsx3 SpeechRecognition keyboard
"""

import re
import time
import threading
import pyttsx3
import speech_recognition as sr
import keyboard
from asi1client import ASI1Client, ASI1ClientError


def is_hardware_command(text: str) -> bool:
    """Detect if text looks like a hardware command or code."""
    return bool(re.search(r"(move_to|pincer|\{|\[|:)", text, re.I))


def speak_text(text: str):
    """Speak text safely in a background thread."""
    if not text.strip():
        return
    if is_hardware_command(text):
        print("\n🤖 Hardware command (not spoken):")
        print(text)
        return

    print(f"\nAI: {text}\n")

    def tts_worker():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(text)
            engine.runAndWait()
            time.sleep(0.1)
            engine.stop()
        except Exception as e:
            print(f"[TTS error] {e}")

    threading.Thread(target=tts_worker, daemon=True).start()


def listen_to_speech(recognizer: sr.Recognizer, mic: sr.Microphone) -> str:
    """Capture speech only while spacebar is pressed."""
    print("\n🎙️ Hold SPACE to talk... (release when done)")

    keyboard.wait("space")

    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        print("🎧 Listening... (release space when finished)")
        audio = recognizer.listen(source, phrase_time_limit=None, timeout=None)

    while keyboard.is_pressed("space"):
        time.sleep(0.05)

    print("🧠 Processing speech...")
    try:
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        print("❌ Could not understand audio.")
    except sr.RequestError:
        print("⚠️ Speech recognition service unavailable.")
    return ""


def main():
    print("=== ASI1 Voice Chat (Press Space to Talk) ===")
    print("Hold SPACEBAR to talk. Say 'exit' or 'quit' to stop.\n")

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    try:
        client = ASI1Client()
    except ASI1ClientError as e:
        print(f"Error initializing ASI1Client: {e}")
        return

    messages = [
        {"role": "system", "content": "You are a helpful AI assistant that can control hardware if asked."}
    ]

    while True:
        user_input = listen_to_speech(recognizer, mic)
        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "stop"}:
            speak_text("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat_completion(messages)
            ai_reply = response["choices"][0]["message"]["content"].strip()
            speak_text(ai_reply)
            messages.append({"role": "assistant", "content": ai_reply})
        except ASI1ClientError as e:
            print(f"[Error] {e}")
            speak_text("There was an error with the AI service.")
        except Exception as e:
            print(f"[Unexpected error] {e}")
            speak_text("Something went wrong.")


if __name__ == "__main__":
    main()
