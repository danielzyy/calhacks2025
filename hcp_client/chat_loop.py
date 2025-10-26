# chat_loop.py
"""
Simple non-streaming chat loop for ASI1Client (Fetch.ai ASI:One Mini)
Make sure you have:
  - asi1client.py in the same directory
  - .env file with ASI1_API_KEY=<your_api_key>
"""

from asi1client import ASI1Client, ASI1ClientError


def main():
    print("=== ASI1 Chat ===")
    print("Type 'exit' or 'quit' to end the session.\n")

    try:
        client = ASI1Client()
    except ASI1ClientError as e:
        print(f"Error initializing ASI1Client: {e}")
        return

    # Keep full conversation for context
    messages = [
        {"role": "system", "content": "You are a helpful and knowledgeable AI assistant."}
    ]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        if not user_input:
            continue

        # Add user message to history
        messages.append({"role": "user", "content": user_input})

        try:
            # Normal (non-streaming) completion
            response = client.chat_completion(messages)
            ai_reply = response["choices"][0]["message"]["content"].strip()

            print(f"AI: {ai_reply}\n")

            # Add assistant message to history
            messages.append({"role": "assistant", "content": ai_reply})

        except ASI1ClientError as e:
            print(f"[Error] {e}")
        except Exception as e:
            print(f"[Unexpected error] {e}")


if __name__ == "__main__":
    main()
