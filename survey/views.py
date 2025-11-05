from django.shortcuts import render
from rest_framework import generics, permissions
from .serializers import ManagerCreateSerializer, USerDetailSerializer

class ManagerCreateView(generics.CreateAPIView):
    serializer_class = ManagerCreateSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

class UserMeView(generics.RetrieveAPIView):
    serializer_class = USerDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

