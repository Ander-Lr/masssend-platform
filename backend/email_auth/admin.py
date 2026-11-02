from django.contrib import admin

from .models import EmailTask, QueueControl, SecurityProfile


@admin.register(SecurityProfile)
class SecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "mfa_enabled", "verification_attempts", "updated_at")
    list_filter = ("status", "mfa_enabled")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmailTask)
class EmailTaskAdmin(admin.ModelAdmin):
    list_display = ("task_type", "recipient", "status", "attempts", "created_at")
    list_filter = ("task_type", "status")
    search_fields = ("recipient", "subject")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["requeue_failed"]

    @admin.action(description="Reintentar tareas fallidas seleccionadas")
    def requeue_failed(self, request, queryset):
        updated = queryset.filter(status=EmailTask.STATUS_FAILED).update(
            status=EmailTask.STATUS_PENDING, attempts=0, error=None,
        )
        self.message_user(request, f"{updated} tarea(s) puestas de nuevo en PENDING.")


@admin.register(QueueControl)
class QueueControlAdmin(admin.ModelAdmin):
    list_display = ("paused",)

    def has_add_permission(self, request):
        # Es un singleton: no tiene sentido crear más de una fila.
        return not QueueControl.objects.exists()
