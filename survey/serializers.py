from django.contrib.auth.models import User
from rest_framework import serializers
from .models import ServicePoint

class ManagerCreateSerializer(serializers.ModelSerializer):
    managed_points = serializers.PrimaryKeyRelatedField(many=True, queryset=ServicePoint.objects.all(), required=False, write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'managed_points')
        extra_kwargs = {'password': {'write_only': True }}
    
    def create(self, validated_data):
        points_data = validated_data.pop('managed_points', None)
        user = User.objects.create_user(**validated_data)

        if points_data:
            user.managed_points.set(points_data)
            
        return user

class USerDetailSerializer(serializers.ModelSerializer):
    managed_points = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'groups', "manged_points")

        