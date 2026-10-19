from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "price", "category")
        widgets = {"price": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}
