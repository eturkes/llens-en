
"""
title: Password Generator
author: Ken Enda
version: 0.2
description: Generates passwords for account provisioning
"""

import secrets


class Tools:
    def __init__(self):
        pass

    def generate_password(
        self,
        length: int = 8,
        count: int = 1,
        use_symbols: bool = False,
    ) -> str:
        """
        Generates passwords for account provisioning.
        Each password contains at least one uppercase letter, one lowercase letter, and one digit.
        Easily confused characters (0 O o 1 l I |) are excluded.

        :param length: Password length. Default 8, minimum 6, maximum 32. Use 10 if unspecified.
        :param count: Number of passwords to generate. Default 1, maximum 5. Use 1 if unspecified.
        :param use_symbols: Whether to include symbols (!@#$%&*+-=?). Default false. If including symbols, 12+ characters recommended.
        :return: Generated password string(s)
        """
        # Validation
        try:
            length = int(length) if length else 10
            count = int(count) if count else 1
        except (TypeError, ValueError):
            length, count = 10, 1

        length = max(6, min(32, length))
        count = max(1, min(5, count))

        uppercase = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        lowercase = "abcdefghijkmnpqrstuvwxyz"
        digits = "23456789"
        symbols = "!@#$%&*+-=?"

        char_groups = [uppercase, lowercase, digits]
        if use_symbols:
            char_groups.append(symbols)

        all_chars = "".join(char_groups)

        passwords = []
        for _ in range(count):
            pwd_chars = [secrets.choice(group) for group in char_groups]
            pwd_chars += [
                secrets.choice(all_chars) for _ in range(length - len(char_groups))
            ]
            for i in range(len(pwd_chars) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                pwd_chars[i], pwd_chars[j] = pwd_chars[j], pwd_chars[i]
            passwords.append("".join(pwd_chars))

        if count == 1:
            return f"Generated password: {passwords[0]}"
        else:
            lines = [f"{i+1}. {p}" for i, p in enumerate(passwords)]
            return "Generated passwords:\n" + "\n".join(lines)
