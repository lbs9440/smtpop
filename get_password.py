import hashlib
import argparse


def hash_password(password):
    """ Hashes the password using SHA256.

    :param password: The password to hash.
    :return: The hashed password.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", "-p", required=True, help="The password to hash.")
    args = parser.parse_args()

    print(hash_password(args.password))

if __name__ == "__main__":
    main()
