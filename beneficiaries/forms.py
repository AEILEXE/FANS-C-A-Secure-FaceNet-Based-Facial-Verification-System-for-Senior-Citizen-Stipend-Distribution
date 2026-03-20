from django import forms
from .models import Beneficiary

PROVINCE_CHOICES = [
    ('', '-- Select Province --'),
    ('Metro Manila (NCR)', 'Metro Manila (NCR)'),
    ('Abra', 'Abra'),
    ('Agusan del Norte', 'Agusan del Norte'),
    ('Agusan del Sur', 'Agusan del Sur'),
    ('Aklan', 'Aklan'),
    ('Albay', 'Albay'),
    ('Antique', 'Antique'),
    ('Apayao', 'Apayao'),
    ('Aurora', 'Aurora'),
    ('Basilan', 'Basilan'),
    ('Bataan', 'Bataan'),
    ('Batanes', 'Batanes'),
    ('Batangas', 'Batangas'),
    ('Benguet', 'Benguet'),
    ('Biliran', 'Biliran'),
    ('Bohol', 'Bohol'),
    ('Bukidnon', 'Bukidnon'),
    ('Bulacan', 'Bulacan'),
    ('Cagayan', 'Cagayan'),
    ('Camarines Norte', 'Camarines Norte'),
    ('Camarines Sur', 'Camarines Sur'),
    ('Camiguin', 'Camiguin'),
    ('Capiz', 'Capiz'),
    ('Catanduanes', 'Catanduanes'),
    ('Cavite', 'Cavite'),
    ('Cebu', 'Cebu'),
    ('Compostela Valley', 'Compostela Valley'),
    ('Cotabato', 'Cotabato'),
    ('Davao del Norte', 'Davao del Norte'),
    ('Davao del Sur', 'Davao del Sur'),
    ('Davao Occidental', 'Davao Occidental'),
    ('Davao Oriental', 'Davao Oriental'),
    ('Dinagat Islands', 'Dinagat Islands'),
    ('Eastern Samar', 'Eastern Samar'),
    ('Guimaras', 'Guimaras'),
    ('Ifugao', 'Ifugao'),
    ('Ilocos Norte', 'Ilocos Norte'),
    ('Ilocos Sur', 'Ilocos Sur'),
    ('Iloilo', 'Iloilo'),
    ('Isabela', 'Isabela'),
    ('Kalinga', 'Kalinga'),
    ('La Union', 'La Union'),
    ('Laguna', 'Laguna'),
    ('Lanao del Norte', 'Lanao del Norte'),
    ('Lanao del Sur', 'Lanao del Sur'),
    ('Leyte', 'Leyte'),
    ('Maguindanao', 'Maguindanao'),
    ('Marinduque', 'Marinduque'),
    ('Masbate', 'Masbate'),
    ('Misamis Occidental', 'Misamis Occidental'),
    ('Misamis Oriental', 'Misamis Oriental'),
    ('Mountain Province', 'Mountain Province'),
    ('Negros Occidental', 'Negros Occidental'),
    ('Negros Oriental', 'Negros Oriental'),
    ('Northern Samar', 'Northern Samar'),
    ('Nueva Ecija', 'Nueva Ecija'),
    ('Nueva Vizcaya', 'Nueva Vizcaya'),
    ('Occidental Mindoro', 'Occidental Mindoro'),
    ('Oriental Mindoro', 'Oriental Mindoro'),
    ('Palawan', 'Palawan'),
    ('Pampanga', 'Pampanga'),
    ('Pangasinan', 'Pangasinan'),
    ('Quezon', 'Quezon'),
    ('Quirino', 'Quirino'),
    ('Rizal', 'Rizal'),
    ('Romblon', 'Romblon'),
    ('Samar', 'Samar'),
    ('Sarangani', 'Sarangani'),
    ('Siquijor', 'Siquijor'),
    ('Sorsogon', 'Sorsogon'),
    ('South Cotabato', 'South Cotabato'),
    ('Southern Leyte', 'Southern Leyte'),
    ('Sultan Kudarat', 'Sultan Kudarat'),
    ('Sulu', 'Sulu'),
    ('Surigao del Norte', 'Surigao del Norte'),
    ('Surigao del Sur', 'Surigao del Sur'),
    ('Tarlac', 'Tarlac'),
    ('Tawi-Tawi', 'Tawi-Tawi'),
    ('Zambales', 'Zambales'),
    ('Zamboanga del Norte', 'Zamboanga del Norte'),
    ('Zamboanga del Sur', 'Zamboanga del Sur'),
    ('Zamboanga Sibugay', 'Zamboanga Sibugay'),
]

VALID_ID_CHOICES = [
    ('', '-- Select ID Type --'),
    ('Senior Citizen ID', 'Senior Citizen ID'),
    ('PhilSys', 'PhilSys ID (National ID)'),
    ('Passport', 'Passport'),
    ('Drivers License', "Driver's License"),
    ('UMID', 'UMID'),
    ('Voters ID', "Voter's ID"),
    ('GSIS', 'GSIS eCard'),
    ('SSS', 'SSS ID'),
    ('Postal ID', 'Postal ID'),
    ('Other', 'Other Government ID'),
]

REP_ID_CHOICES = [
    ('', '-- Select ID Type --'),
    ('PhilSys', 'PhilSys ID'),
    ('Passport', 'Passport'),
    ('Drivers License', "Driver's License"),
    ('UMID', 'UMID'),
    ('Voters ID', "Voter's ID"),
    ('Senior Citizen ID', 'Senior Citizen ID'),
    ('Other', 'Other'),
]


class BeneficiaryInfoForm(forms.ModelForm):
    province = forms.ChoiceField(
        choices=PROVINCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_province', 'required': True}),
    )
    municipality = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_municipality',
            'placeholder': 'Select province first...',
            'required': True,
        }),
    )
    barangay = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_barangay',
            'placeholder': 'Enter barangay...',
            'required': True,
        }),
    )

    class Meta:
        model = Beneficiary
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth',
            'gender', 'address', 'barangay', 'municipality', 'province',
            'contact_number', 'senior_citizen_id', 'valid_id_type', 'valid_id_number',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': True}),
            'gender': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'required': True}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'senior_citizen_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SC-2024-00123'}),
            'valid_id_type': forms.Select(attrs={'class': 'form-select'}, choices=VALID_ID_CHOICES),
            'valid_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID number'}),
        }

    def clean_date_of_birth(self):
        import datetime
        dob = self.cleaned_data['date_of_birth']
        today = datetime.date.today()
        age = (today - dob).days // 365
        if age < 60:
            raise forms.ValidationError('Beneficiary must be at least 60 years old.')
        return dob

    def clean_province(self):
        province = self.cleaned_data.get('province')
        if not province:
            raise forms.ValidationError('Please select a province.')
        return province


class BeneficiaryEditForm(forms.ModelForm):
    """Edit form for existing beneficiaries — all personal fields except face."""
    province = forms.ChoiceField(
        choices=PROVINCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_province'}),
    )
    municipality = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_municipality',
        }),
    )
    barangay = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_barangay',
        }),
    )

    class Meta:
        model = Beneficiary
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth',
            'gender', 'address', 'barangay', 'municipality', 'province',
            'contact_number', 'senior_citizen_id', 'valid_id_type', 'valid_id_number',
            'has_representative', 'rep_first_name', 'rep_last_name',
            'rep_relationship', 'rep_contact', 'rep_id_type', 'rep_id_number',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'senior_citizen_id': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_id_type': forms.Select(attrs={'class': 'form-select'}, choices=VALID_ID_CHOICES),
            'valid_id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'has_representative': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'hasRep'}),
            'rep_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'rep_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'rep_relationship': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Son, Daughter, Spouse'}),
            'rep_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'rep_id_type': forms.Select(attrs={'class': 'form-select'}, choices=REP_ID_CHOICES),
            'rep_id_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_province(self):
        province = self.cleaned_data.get('province')
        if not province:
            raise forms.ValidationError('Please select a province.')
        return province


class RepresentativeForm(forms.ModelForm):
    class Meta:
        model = Beneficiary
        fields = [
            'has_representative', 'rep_first_name', 'rep_last_name',
            'rep_relationship', 'rep_contact', 'rep_id_type', 'rep_id_number',
        ]
        widgets = {
            'has_representative': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'hasRep'}),
            'rep_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'rep_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'rep_relationship': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Son, Daughter, Spouse'}),
            'rep_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'rep_id_type': forms.Select(attrs={'class': 'form-select'}, choices=REP_ID_CHOICES),
            'rep_id_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ConsentForm(forms.Form):
    consent = forms.BooleanField(
        required=True,
        label='I consent to the collection and processing of my biometric data for the purpose of stipend distribution verification.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    consent_privacy = forms.BooleanField(
        required=True,
        label='I have read and understood the Privacy Notice above.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
