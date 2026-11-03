from django.urls import path

from masssend.interfaces.http.contactos import vistas as v

# Las rutas fijas van antes que contactos/<id> para que no se confundan con un id.
urlpatterns = [
    path("contactos", v.ContactosVista.as_view()),
    path("contactos/etiquetas", v.EtiquetasVista.as_view()),
    path("contactos/eliminar-lote", v.EliminarLoteVista.as_view()),
    path("contactos/importar", v.ImportarVista.as_view()),
    path("contactos/<str:contacto_id>", v.ContactoVista.as_view()),
]
