from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name')

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value.strip()).exists():
            raise serializers.ValidationError('A user with that username already exists.')
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError('A user with that email already exists.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'date_joined',
            'is_staff',
            'is_active',
        )
        read_only_fields = ('id', 'date_joined', 'is_staff', 'is_active')

    def validate_email(self, value):
        user = self.instance
        if user and value and User.objects.exclude(pk=user.pk).filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError('A user with that email already exists.')
        return value

    def validate_username(self, value):
        user = self.instance
        if user and User.objects.exclude(pk=user.pk).filter(username__iexact=value).exists():
            raise serializers.ValidationError('A user with that username already exists.')
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    def validate_new_password(self, value):
        validate_password(value)
        return value
