"""Multi-factor biometric enrollment protocol.

Enrollment is the process by which a new participant:

1. Captures multiple biometric factors on their device (fingerprint, face,
   iris, voice — at least two required).
2. Each capture is hashed into a local template (raw data discarded).
3. A cryptographic keypair is generated on-device.
4. The **public key** and the list of enrolled factor *types* (but NOT the
   templates) are sent to the server and stored in the registry.
5. The server returns an anonymous participant ID.

After enrollment the participant can verify their identity via the
challenge-response protocol in ``verification.py``.
"""

from __future__ import annotations

from opendemocracy.identity.biometrics import validate_factor_set
from opendemocracy.identity.crypto import generate_keypair
from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import BiometricTemplate, EnrollmentRecord


def enroll(
    templates: list[BiometricTemplate],
    registry: IdentityRegistry,
) -> EnrollmentRecord:
    """Enroll a new participant using multiple biometric factors.

    Parameters
    ----------
    templates:
        Locally-created biometric templates (one per factor).  These are
        used only to confirm the enrollment is well-formed — they are
        **not** transmitted or stored by the server.
    registry:
        The server-side identity registry.

    Returns
    -------
    EnrollmentRecord
        The server-side record containing the anonymous ID and public key.

    Raises
    ------
    ValueError
        If the set of biometric factors is invalid (too few, duplicates).
    RuntimeError
        If the public key is already registered (possible duplicate person).
    """
    factors = [t.factor for t in templates]

    problems = validate_factor_set(factors)
    if problems:
        raise ValueError("; ".join(problems))

    # Generate keypair on-device.
    _private_key, public_key = generate_keypair()

    # Check that this public key isn't already enrolled.
    if registry.lookup_by_public_key(public_key) is not None:
        raise RuntimeError("A participant with this public key is already enrolled")

    # Register with the server (only public key + factor types).
    record = EnrollmentRecord(
        public_key=public_key,
        factors_enrolled=factors,
    )
    registry.register(record)

    return record
