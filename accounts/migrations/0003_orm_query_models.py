from django.db import migrations, models
import django.db.models.deletion


def move_product_categories(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Category = apps.get_model("accounts", "Category")
    Product = apps.get_model("accounts", "Product")
    for product in Product.objects.using(db_alias).all().iterator():
        category, _ = Category.objects.using(db_alias).get_or_create(name=product.category)
        Product.objects.using(db_alias).filter(pk=product.pk).update(category_fk_id=category.pk)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_product")]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name="product",
            name="category_fk",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="accounts.category"),
        ),
        migrations.RunPython(move_product_categories, migrations.RunPython.noop),
        migrations.RemoveField(model_name="product", name="category"),
        migrations.RenameField(model_name="product", old_name="category_fk", new_name="category"),
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="accounts.category"),
        ),
        migrations.CreateModel(
            name="Restaurant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("cuisine", models.CharField(max_length=100)),
                ("rating", models.DecimalField(decimal_places=1, max_digits=2)),
            ],
        ),
        migrations.CreateModel(
            name="Movie",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name="Review",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reviewer_name", models.CharField(max_length=100)),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("movie", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="accounts.movie")),
            ],
        ),
    ]
