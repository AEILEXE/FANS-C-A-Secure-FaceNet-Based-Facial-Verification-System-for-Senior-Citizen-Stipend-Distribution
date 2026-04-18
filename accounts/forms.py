from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm as _DjPasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser

# Active role choices — excludes the legacy 'admin' role from new-user UI.
# The 'admin' DB value is kept in the model so existing rows are never broken,
# but staff should never create new users with that role.
_ACTIVE_ROLE_CHOICES = [
    (CustomUser.ROLE_HEAD_BRGY, 'Head Barangay'),
    (CustomUser.ROLE_ADMIN_IT,  'IT / Admin'),
    (CustomUser.ROLE_STAFF,     'Staff'),
]


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Minimum 8 characters. Must not be entirely numeric or a common password.',
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'employee_id', 'phone']
        widgets = {
            'username':    forms.TextInput(attrs={'class': 'form-control'}),
            'first_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':   forms.TextInput(attrs={'class': 'form-control'}),
            'email':       forms.EmailInput(attrs={'class': 'form-control'}),
            'role':        forms.Select(attrs={'class': 'form-select'},
                                        choices=_ACTIVE_ROLE_CHOICES),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'phone':       forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Enforce active-only choices even if the model field carries legacy values
        self.fields['role'].choices = _ACTIVE_ROLE_CHOICES

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return p2

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        if p1:
            # Run Django's full password validation suite (min length, common, numeric)
            user = self.instance
            validate_password(p1, user=user)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'role', 'employee_id',
                  'phone', 'profile_picture', 'is_active']
        widgets = {
            'first_name':      forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':       forms.TextInput(attrs={'class': 'form-control'}),
            'email':           forms.EmailInput(attrs={'class': 'form-control'}),
            'role':            forms.Select(attrs={'class': 'form-select'},
                                            choices=_ACTIVE_ROLE_CHOICES),
            'employee_id':     forms.TextInput(attrs={'class': 'form-control'}),
            'phone':           forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = _ACTIVE_ROLE_CHOICES


class PasswordChangeForm(_DjPasswordChangeForm):
    """Self-service password change for the currently logged-in user."""
    old_password = forms.CharField(
        label='Current Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'current-password'}),
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Minimum 8 characters. Must not be entirely numeric or a common password.',
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )


class AdminPasswordResetForm(forms.Form):
    """Admin resets another user's password without knowing the old one."""
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Minimum 8 characters. Must not be entirely numeric or a common password.',
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1')
        p2 = cleaned.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        if p1:
            validate_password(p1)
        return cleaned
