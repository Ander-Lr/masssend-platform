from django import forms
from django.core.exceptions import ValidationError
import re
from .models import Contact


class PhoneEcuadorWidget(forms.TextInput):
    """
    Widget de input para numero de telefono con bandera de Ecuador y prefijo +593 fijo.
    Muestra: [Bandera Ecuador] [+593] [input solo los digitos locales]
    Al guardar reconstruye el numero completo: 593XXXXXXXXX
    """

    def render(self, name, value, attrs=None, renderer=None):
        # Si el valor ya contiene 593 al inicio, mostrar solo la parte local
        display_value = value or ''
        if display_value.startswith('593'):
            display_value = display_value[3:]
        elif display_value.startswith('+593'):
            display_value = display_value[4:]

        attrs = attrs or {}
        attrs['placeholder'] = '9XXXXXXXX'
        attrs['maxlength']   = '10'
        attrs['style']       = (
            'border-left: none; border-radius: 0 8px 8px 0; '
            'padding: 8px 12px; font-size: 0.92rem; '
            'width: 100%; box-sizing: border-box;'
        )
        attrs['id'] = attrs.get('id', f'id_{name}')

        input_html = super().render(name, display_value, attrs, renderer)

        return f"""
        <div style="display: flex; align-items: stretch; max-width: 480px;">
            <div style="
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 8px 12px;
                background: #f5f3ff;
                border: 1px solid #d1d5db;
                border-right: none;
                border-radius: 8px 0 0 8px;
                font-size: 0.92rem;
                font-weight: 700;
                color: #3730a3;
                white-space: nowrap;
                flex-shrink: 0;
            ">
                <img src="https://flagcdn.com/w20/ec.png"
                     srcset="https://flagcdn.com/w40/ec.png 2x"
                     width="20" height="14"
                     alt="Ecuador"
                     style="border-radius: 2px; display: inline-block;">
                +593
            </div>
            {input_html}
        </div>
        <div id="phone-hint-{name}" style="
            margin-top: 5px;
            font-size: 0.77rem;
            color: #888;
        ">
            Ingresa los digitos sin el 0 inicial. Ejemplo: para 0999123456 escribe 999123456
        </div>
        <div id="phone-error-{name}" style="
            margin-top: 5px;
            font-size: 0.8rem;
            color: #dc2626;
            display: none;
            font-weight: 600;
        "></div>

        <script>
        (function() {{
            const input = document.getElementById('{attrs['id']}');
            const errBox = document.getElementById('phone-error-{name}');
            if (!input) return;

            input.addEventListener('input', function() {{
                const val = this.value.replace(/\\D/g, '');
                this.value = val;  // solo numeros

                // Quitar 0 inicial si el usuario lo pone
                if (val.startsWith('0')) {{
                    this.value = val.substring(1);
                }}

                // Validacion en tiempo real
                const len = this.value.length;
                if (len > 0 && len < 9) {{
                    errBox.textContent = 'El numero es muy corto. Debe tener 9 digitos (sin el 0 inicial).';
                    errBox.style.display = 'block';
                    this.style.borderColor = '#dc2626';
                }} else if (len > 10) {{
                    errBox.textContent = 'El numero es muy largo.';
                    errBox.style.display = 'block';
                    this.style.borderColor = '#dc2626';
                }} else {{
                    errBox.style.display = 'none';
                    this.style.borderColor = '#d1d5db';
                }}
            }});
        }})();
        </script>
        """

    def value_from_datadict(self, data, files, name):
        """Al recibir el formulario, reconstruir el numero completo con prefijo 593."""
        raw = super().value_from_datadict(data, files, name) or ''
        digits = re.sub(r'\D', '', raw)

        # Quitar 0 inicial si viene
        if digits.startswith('0'):
            digits = digits[1:]

        # Agregar prefijo 593 si no lo tiene
        if digits and not digits.startswith('593'):
            digits = '593' + digits

        return digits


class ContactAdminForm(forms.ModelForm):
    """Formulario con validacion completa del numero de telefono ecuatoriano."""

    class Meta:
        model = Contact
        fields = '__all__'
        widgets = {
            'phone_number': PhoneEcuadorWidget(),
        }

    def clean_phone_number(self):
        numero = self.cleaned_data.get('phone_number', '').strip()

        # Solo digitos
        digits = re.sub(r'\D', '', numero)

        # Debe empezar con 593
        if not digits.startswith('593'):
            raise ValidationError(
                'El numero debe incluir el prefijo de Ecuador (593). '
                'Ejemplo correcto: 593999123456'
            )

        # La parte local (sin 593)
        local = digits[3:]

        if len(local) < 9:
            raise ValidationError(
                f'El numero local es demasiado corto ({len(local)} digitos). '
                'Un numero movil ecuatoriano tiene 9 digitos sin el 0 inicial. '
                'Ejemplo: 999123456'
            )

        if len(local) > 10:
            raise ValidationError(
                f'El numero es demasiado largo ({len(local)} digitos despues del 593). '
                'Revisa que no haya digitos de mas.'
            )

        # Numeros moviles Ecuador: empiezan en 9 (09X)
        # Fijos Quito: 2, Guayaquil: 4, etc.
        if len(local) == 9 and not local.startswith('9'):
            raise ValidationError(
                'Los numeros moviles ecuatorianos empiezan con 9. '
                f'El numero ingresado empieza con {local[0]}. '
                'Ejemplo movil: 593999123456'
            )

        # Retornar formato normalizado: 593 + 9 digitos locales
        return digits
