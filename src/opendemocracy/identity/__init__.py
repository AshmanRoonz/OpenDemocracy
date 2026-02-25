"""Identity layer: multi-factor biometric enrollment and verification.

Architecture
------------
Biometric data is captured and stored **exclusively on the user's device**.
The server never sees raw biometric templates.  During enrollment the device
generates a cryptographic keypair, proves possession of multiple biometric
factors locally, and registers only the *public* key with the server.

Verification uses a challenge-response protocol: the server issues a random
nonce, the device authenticates the user via local biometrics, signs the
nonce with the private key, and the server verifies the signature against
the stored public key.

This guarantees **one person → one key → one vote** without any biometric
data crossing the network.
"""
