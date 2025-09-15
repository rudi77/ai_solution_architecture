import random
import string

def generate_password(length=12, use_uppercase=True, use_digits=True, use_special=True):
    chars = string.ascii_lowercase
    if use_uppercase:
        chars += string.ascii_uppercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Random Password Generator")
    parser.add_argument('-l', '--length', type=int, default=12, help='Password length (default: 12)')
    parser.add_argument('--no-uppercase', action='store_true', help='Exclude uppercase letters')
    parser.add_argument('--no-digits', action='store_true', help='Exclude digits')
    parser.add_argument('--no-special', action='store_true', help='Exclude special characters')
    args = parser.parse_args()

    password = generate_password(
        length=args.length,
        use_uppercase=not args.no_uppercase,
        use_digits=not args.no_digits,
        use_special=not args.no_special
    )
    print(f"Generated password: {password}")
