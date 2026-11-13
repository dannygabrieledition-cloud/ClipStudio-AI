# ClipStudio AI — Edición Web

Aplicación Streamlit para analizar archivos de video autorizados, sugerir momentos a partir del habla, crear subtítulos y exportar clips MP4 verticales en 720×1280.

## Publicación (sin instalar Python en tu PC)

1. Entra en https://github.com y crea una cuenta gratuita (si no tienes una).
2. Crea un repositorio **privado** llamado `clipstudio-ai-web` (puedes optar por público si no te importa compartir el código). Extrae este ZIP y sube el **contenido** de esta carpeta al repositorio, incluidos `app.py`, `engine.py`, `requirements.txt`, `packages.txt` y la carpeta `.streamlit`. No subas videos de clientes al repositorio.
3. Entra en https://share.streamlit.io e inicia sesión con GitHub.
4. Pulsa **Create app**, selecciona el repositorio y la rama, e indica **Main file path** = `app.py`.
5. Si se ofrece la opción, selecciona **Python 3.11** para evitar incompatibilidades. El despliegue instalará las dependencias automáticamente.
6. Opcional pero recomendado: en **Advanced settings / Secrets**, agrega `APP_PASSWORD = "tu_contraseña_larga"` para proteger la interfaz compartida. No pongas contraseñas en el código ni en GitHub.
7. Pulsa **Deploy**. Obtendrás una URL terminada en `streamlit.app` para abrir la app desde el navegador.

## Primera prueba

- Usa un video MP4 propio/autorizado de **1–3 minutos**, **menos de 100 MB**, con voz clara.
- Selecciona **tiny**, 1–2 clips y 20–30 segundos.
- Marca la confirmación de autorización y pulsa **Generar clips**.
- Revisa los resultados y descarga los MP4 o el ZIP.

## Importante

- **No es un sitio web ya publicado**: el ZIP está preparado para que lo publiques en tu propia cuenta.
- **No descarga videos de YouTube**; pide el archivo original al titular con permiso de edición.
- La puntuación de clips es una heurística de texto, no una predicción de viralidad.
- Los subtítulos se transcriben automáticamente y pueden tener errores; verifica datos y nombres.
- En alojamiento gratuito, los videos largos y muchos clips pueden provocar falta de memoria o reinicios. Para producción con videos de 30–60 minutos, utiliza servidor de pago y trabajos en segundo plano.
- La versión inicial trabaja con archivos temporales y almacena las salidas en la sesión; no es un sistema multiusuario, ni un almacenamiento seguro de videos confidenciales.

## Archivos

- `app.py`: interfaz web Streamlit.
- `engine.py`: transcripción, selección y render FFmpeg.
- `requirements.txt`: dependencias Python.
- `packages.txt`: instala FFmpeg en la nube.
- `.streamlit/config.toml`: límites de subida y aspecto.
- `.python-version`: versión recomendada de Python.
