from django.contrib.auth.tokens import PasswordResetTokenGenerator


class ActivationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "betboy.customer.activation.v1"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}:{user.password}:{user.email}:{user.is_active}:{timestamp}"


activation_token = ActivationTokenGenerator()
