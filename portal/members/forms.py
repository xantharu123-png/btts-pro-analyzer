from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError

from .copy import COPY
from .models import User


class RegisterForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput, strip=False, max_length=128)
    password_confirm = forms.CharField(widget=forms.PasswordInput, strip=False, max_length=128)
    accept = forms.BooleanField()

    def __init__(self, *args, lang="de", **kwargs):
        super().__init__(*args, **kwargs)
        self.words = COPY[lang]
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
        self.fields["email"].label = self.words["email"]
        self.fields["email"].widget.attrs.update(autocomplete="email", inputmode="email")
        for key, label in [("password", "password"), ("password_confirm", "repeat_password")]:
            self.fields[key].label = self.words[label]
            self.fields[key].widget.attrs["autocomplete"] = "new-password"
        self.fields["password"].help_text = self.words["password_help"]
        self.fields["accept"].label = self.words["accept_terms"]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        data = super().clean()
        password = data.get("password")
        if password:
            if password != data.get("password_confirm"):
                self.add_error("password_confirm", self.words["password_mismatch"])
            try:
                password_validation.validate_password(password, User(email=data.get("email", "")))
            except ValidationError as exc:
                self.add_error("password", exc)
        return data


class LoginForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput, strip=False, max_length=128)

    def __init__(self, *args, request=None, lang="de", **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.words = COPY[lang]
        self.user = None
        for name, field in self.fields.items():
            field.label = self.words[name]
            field.widget.attrs.update({"class": "input", "autocomplete": "username" if name == "email" else "current-password"})

    def clean(self):
        data = super().clean()
        if data.get("email") and data.get("password"):
            self.user = authenticate(self.request, email=data["email"].strip().lower(), password=data["password"])
            if self.user is None:
                raise ValidationError(self.words["login_error"])
        return data


class ResetRequestForm(forms.Form):
    email = forms.EmailField(max_length=254)

    def __init__(self, *args, lang="de", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = COPY[lang]["email"]
        self.fields["email"].widget.attrs.update({"class": "input", "autocomplete": "email"})


class ResetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.max_length = 128
            field.widget.attrs.update({"class": "input", "autocomplete": "new-password", "maxlength": "128"})
