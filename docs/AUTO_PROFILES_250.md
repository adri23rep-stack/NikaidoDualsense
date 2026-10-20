# Perfiles automáticos 2.0

Nikaido 2.5 reemplaza la búsqueda simple de procesos por reglas ordenadas y restauración automática.

Cada regla puede incluir:

- ejecutable;
- ruta exacta opcional;
- parte del título de la ventana;
- perfil de Nikaido;
- prioridad;
- funcionamiento solo con el juego al frente o mientras siga abierto;
- retrasos de entrada y salida para evitar cambios por ventanas breves.

Cuando una regla comienza, Nikaido recuerda el perfil que estaba activo. Cuando termina, restaura ese perfil. Un cambio manual realizado durante el juego se convierte en el nuevo perfil de regreso y no es pisado de inmediato.

Los mapas antiguos `juego.exe → perfil` siguen funcionando como reglas de respaldo y no se eliminan durante la migración.
