"""Emit canvas.ts for a locale using nl structure and Italian values from ES file.

Spanish (es) and Dutch (nl) share the same 506 key order. Values are read from
es/canvas.ts with a line/phrase map to Italian, then re-emitted with nl breaks.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NL = ROOT / "src/locales/messages/nl/canvas.ts"
ES = ROOT / "src/locales/messages/es/canvas.ts"
OUT_IT = ROOT / "src/locales/messages/it/canvas.ts"


def decode_ts_string(raw_inner: str) -> str:
    out: list[str] = []
    idx = 0
    while idx < len(raw_inner):
        if raw_inner[idx] == "\\" and idx + 1 < len(raw_inner):
            nxt = raw_inner[idx + 1]
            if nxt == "'":
                out.append("'")
                idx += 2
            elif nxt == "\\":
                out.append("\\")
                idx += 2
            else:
                out.append(raw_inner[idx])
                idx += 1
        else:
            out.append(raw_inner[idx])
            idx += 1
    return "".join(out)


def parse_values_ordered(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    values: list[str] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        rest = match.group(2).strip()
        if rest == "":
            idx += 1
            val_line = lines[idx].strip()
            if val_line.endswith(","):
                val_line = val_line[:-1].strip()
            assert val_line.startswith("'") and val_line.endswith("'")
            values.append(decode_ts_string(val_line[1:-1]))
            idx += 1
        else:
            raw = rest
            if raw.endswith(","):
                raw = raw[:-1].strip()
            assert raw.startswith("'") and raw.endswith("'")
            values.append(decode_ts_string(raw[1:-1]))
            idx += 1
    return values


def nl_key_multiline_rows(text: str) -> list[tuple[str, bool]]:
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    rows: list[tuple[str, bool]] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^(\s*)'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        key, rest = match.group(2), match.group(3).strip()
        if rest == "":
            rows.append((key, True))
            idx += 2
        else:
            rows.append((key, False))
            idx += 1
    return rows


def encode_ts_single_quoted(value: str) -> str:
    parts: list[str] = []
    for char in value:
        if char == "\\":
            parts.append("\\\\")
        elif char == "'":
            parts.append("\\'")
        else:
            parts.append(char)
    return "".join(parts)


def spanish_to_italian(value: str) -> str:
    """Map es tier-27 canvas strings to Italian (phrase-safe order: longest first)."""
    pairs: list[tuple[str, str]] = [
        ("¿Seguro?", "Sei sicuro?"),
        ("Hola {username}, soy tu asistente de pensamiento visual con IA",
         "Ciao {username}, sono il tuo assistente IA per il pensiero visivo"),
        ("Introduzca el código de invitación (xxx-xxx) para unirse a su sesión.",
         "Inserisci il codice di invito (xxx-xxx) per unirti alla loro sessione."),
        ("No hay sesiones escolares ahora. Un compañero debe iniciar «Colaboración escolar» en el lienzo.",
         (
             "Nessuna sessione scolastica attiva. Un collega deve avviare la "
             "«Collaborazione scolastica» sull'area di disegno."
         )),
        ("Error de red al unirse", "Errore di rete: impossibile partecipare"),
        ("No se pudieron cargar las sesiones escolares",
         "Impossibile caricare le sessioni scolastiche"),
        ("Error al unirse a la presentazione",
         "Impossibile partecipare alla presentazione"),
        ("Error al unirse", "Impossibile partecipare"),
        ("Describa su diagrama o elija una plantilla abajo...",
         "Descrivi il diagramma o scegli un modello qui sotto..."),
        ("Describa su diagrama o elija una plantilla abajo…",
         "Descrivi il diagramma o scegli un modello qui sotto…"),
        ("Introduzca el código de presentación completo",
         "Inserisci il codice di presentazione completo"),
        ("Formato de código de presentación no válido (debe ser xxx-xxx)",
         "Formato del codice di presentazione non valido (deve essere xxx-xxx)"),
        ("Cree en el lienzo", "Crea sull’area di disegno"),
        ("Mapa de árbol (Tree Map)", "Mappa ad albero (Tree Map)"),
        ("Mapa multiflujo (Multi-Flow Map)", "Mappa multi-flusso (Multi-Flow Map)"),
        ("Mapa mental (Mind Map)", "Mappa mentale (Mind Map)"),
        ("Mapa de flujo (Flow Map)", "Mappa di flusso (Flow Map)"),
        ("Mapa de doble burbuja (Double Bubble Map)", "Mappa a doppia bolla (Double Bubble Map)"),
        ("Mapa conceptual (Concept Map)", "Mappa concettuale (Concept Map)"),
        ("Mapa circular (Circle Map)", "Mappa circolare (Circle Map)"),
        ("Mapa burbuja (Bubble Map)", "Mappa a bolle (Bubble Map)"),
        ("Mapa puente (Bridge Map)", "Mappa a ponte (Bridge Map)"),
        ("Mapa de llaves (Brace Map)", "Mappa a parentesi (Brace Map)"),
        ("Espacio lleno; el autoguardado no está disponible por ahora. Elimine diagramas para liberar espacio.",
         "Spazio pieno: il salvataggio automatico non è disponibile. Elimina diagrammi per liberare spazio."),
        ("Elija el tipo de diagrama", "Scegli il tipo di diagramma"),
        ("Diagrama nuevo", "Nuovo diagramma"),
        ("Ajustar a la pantalla", "Adatta allo schermo"),
        ("Exportar imagen", "Esporta immagine"),
        ("Inicie sesión para guardar", "Accedi per salvare"),
        ("Guardado hace {n} min", "Salvato {n} min fa"),
        ("Guardado hace {n}s", "Salvato {n} s fa"),
        ("Guardado hace un momento", "Salvato poco fa"),
        ("Guardado a las {time}", "Salvato alle {time}"),
        ("Introduzca la relación...", "Inserisci la relazione..."),
        ("Pulse 1–5 para seleccionar", "Premi 1–5 per selezionare"),
        ("pulse para especificar...", "clic per specificare..."),
        ("[Pulse para establecer]", "[Clic per impostare]"),
        ("Pregunta de enfoque:", "Domanda focale:"),
        ("[Las alternativas aparecerán aquí]", "[Le alternative appariranno qui]"),
        ("IA...", "IA..."),
        ("Falló la solicitud de validación", "Richiesta di convalida non riuscita"),
        ("Sin resultado", "Nessun risultato"),
        ("Mano (arrastrar)", "Mano"),
        ("Haga clic para restaurar la instantánea {n} · Ctrl+Clic para eliminar",
         "Clic per ripristinare l’istantanea {n} · Ctrl+clic per eliminare"),
        ("No se pudo eliminar la instantánea; inténtelo de nuevo",
         "Impossibile eliminare l’istantanea, riprova"),
        ("Instantánea {n} eliminada", "Istantanea {n} eliminata"),
        ("No se pudo restaurar la instantánea; inténtelo de nuevo",
         "Impossibile ripristinare l’istantanea, riprova"),
        ("Antes de restaurar la instantánea {n}", "Prima del ripristino dell’istantanea {n}"),
        ("¿Restaurar la instantánea {n}? Se reemplazarán los cambios actuales.",
         "Ripristinare l’istantanea {n}? Le modifiche attuali saranno sostituite."),
        ("Restaurar instantánea", "Ripristina istantanea"),
        ("Restaurar instantánea {n}", "Ripristina istantanea {n}"),
        ("Diseño didáctico", "Progettazione didattica"),
        ("Colaboración compartida", "Collaborazione condivisa"),
        ("Compartir en la comunidad", "Condividi con la community"),
        ("Colaboración escolar", "Collaborazione scolastica"),
        ("Restablecer plantilla predeterminada", "Ripristina modello predefinito"),
        ("Exportar como archivo MG", "Esporta come file MG"),
        ("Haga clic para editar el nombre del archivo",
         "Clic per modificare il nome del file"),
        ("Colaborar (escolar o compartido)", "Collabora (scuola o condivisa)"),
        ("Haga clic para administrar el espacio de la galería",
         "Clic per gestire lo spazio in galleria"),
        ("Haga clic para guardar", "Clic per salvare"),
        ("Vista de alambre", "Schema a blocchi"),
        ("Actualizar estilo de texto", "Aggiorna stile del testo"),
        ("Actualizar borde", "Aggiorna bordo"),
        ("Actualizar fondo", "Aggiorna sfondo"),
        ("Cambiar dirección", "Inverti direzione"),
        ("Próximamente", "Prossimamente"),
        ("Popular", "Popolare"),
        ("Vuelta al modo normal", "Tornato alla modalità normale"),
        ("Modo hoja de aprendizaje activato", "Passato alla modalità scheda di studio"),
        ("Subpaso {n}.2", "Sottopasso {n}.2"),
        ("Subpaso {n}.1", "Sottopasso {n}.1"),
        ("Subparte 2", "Sottoparte 2"),
        ("Subparte 1", "Sottoparte 1"),
        ("Vivo", "Vivace"),
        ("Sencillo", "Semplice"),
        ("Profesional", "Business"),
        ("Seleccione un paso para añadir un subpaso",
         "Seleziona un passaggio per aggiungere un sottopasso"),
        ("Seleccione primero un nodo de similitud o diferencia",
         "Seleziona prima un nodo di somiglianza o differenza"),
        ("Seleccione nodos de similitud o diferencia (los nodos tema no se pueden eliminar)",
         "Seleziona nodi di somiglianza o differenza (i nodi tema non possono essere eliminati)"),
        ("Seleccione un nodo de parte y pulse Intro para añadir una subparte",
         "Seleziona un nodo parte e premi Invio per aggiungere una sottoparte"),
        ("Seleccione una parte para añadir una subparte",
         "Seleziona una parte a cui aggiungere una sottoparte"),
        ("Seleccione nodos para eliminar", "Seleziona i nodi da eliminare"),
        ("Seleccione primero uno o más nodos", "Seleziona prima uno o più nodi"),
        ("Seleccione nodos de categoría u hoja (el nodo tema no se puede eliminar)",
         "Seleziona nodi categoria o foglia (il nodo tema non può essere eliminato)"),
        ("Seleccione una rama o un nodo hijo", "Seleziona un ramo o un nodo figlio"),
        ("Preajustes", "Preimpostazioni"),
        ("Parte añadida", "Parte aggiunta"),
        ("Nodo añadido", "Nodo aggiunto"),
        ("Nuevo subpaso", "Nuovo sottopasso"),
        ("Nueva subparte", "Nuova sottoparte"),
        ("Nuevo paso", "Nuovo passaggio"),
        ("Nueva parte", "Nuova parte"),
        ("Elemento B nuevo", "Nuovo elemento B"),
        ("Elemento A nuevo", "Nuovo elemento A"),
        ("Nuevo efecto", "Nuovo effetto"),
        ("Nuevo hijo", "Nuovo figlio"),
        ("Nueva causa", "Nuova causa"),
        ("Nueva rama", "Nuovo ramo"),
        ("Nuevo atributo", "Nuovo attributo"),
        ("Nueva asociación", "Nuova associazione"),
        ("No se pudo guardar la instantánea; inténtelo de nuevo",
         "Impossibile salvare l’istantanea, riprova"),
        ("Instantánea {n} guardada", "Istantanea {n} salvata"),
        ("Guarde primero el diagrama antes de tomar una instantánea",
         "Salva prima il diagramma prima di creare un’istantanea"),
        ("Pulse dos veces el texto de un nodo primero y luego escriba con el teclado",
         "Fai doppio clic sull’etichetta di un nodo, poi digita con la tastiera"),
        ("Cerrar teclado", "Chiudi tastiera"),
        ("Teclado en pantalla sincronizado con el idioma de la interfaz",
         "Tastiera su schermo sincronizzata con la lingua dell’interfaccia"),
        ("Teclado virtual", "Tastiera virtuale"),
        ("Guarde una versión de este diagrama (máx. 10)",
         "Salva una versione di questo diagramma (max 10)"),
        ("Instantánea", "Istantanea"),
        ("Más aplicaciones", "Altre app"),
        ("Seleccione nodos por lotes; haga visible el pensamiento divergente y convergente",
         "Seleziona più nodi; rendi visibile il pensiero divergente e convergente"),
        ("Cascada", "Waterfall"),
        ("Huecos aleatorios para estudiar y repasar",
         "Spazi vuoti casuali per studiare e ripassare"),
        ("Hoja de aprendizaje", "Scheda di studio"),
        ("Modo estándar por ahora; más modos próximamente",
         "Modalità standard per ora; altre modalità in arrivo"),
        ("Modos de mapa conceptual", "Modalità mappa concettuale"),
        ("Hoja de aprendizaje restaurada", "Scheda di studio ripristinata"),
        ("Dirección del diseño cambiada", "Direzione del layout invertita"),
        ("Copiar formato", "Copia formato"),
        ("Formato", "Formato"),
        ("Seleccione primero un nodo origen", "Seleziona prima un nodo sorgente"),
        ("El copiador de formato está en desarrollo", "La copia formato è in sviluppo"),
        ("Copiador de formato cancelado", "Copia formato annullata"),
        ("Formato aplicado a {count} nodo(s)", "Formato applicato a {count} nodo/i"),
        ("Estilo copiado — seleccione nodos destino y pulse de nuevo para aplicar",
         "Stile copiato — seleziona i nodi di destinazione e clic di nuovo per applicare"),
        ("Inglés", "Inglese"),
        ("Chino", "Cinese"),
        ("{name} está en desarrollo", "{name} è in sviluppo"),
        ("Color del marcador resaltador", "Colore evidenziatore"),
        ("Salir de la presentazione", "Esci dalla presentazione"),
        ("Borrar marcador resaltador", "Cancella evidenziatore"),
        ("Foco (spotlight)", "Spotlight"),
        ("Puntero láser", "Puntatore laser"),
        ("Salir", "Esci"),
        ("Restablecer", "Reimposta"),
        ("Pausa", "Pausa"),
        ("Iniciar", "Avvia"),
        ("Establecer", "Imposta"),
        ("Minutos", "Minuti"),
        ("Temporizador de presentación", "Timer presentazione"),
        ("Temporizador", "Timer"),
        ("Bolígrafo", "Penna"),
        ("Marcador resaltador", "Evidenziatore"),
        ("Herramientas de presentación", "Strumenti presentazione"),
        ("Yeso", "Gesso"),
        ("Tiza", "Gesso"),
        ("Vinagre", "Aceto"),
        ("Lejía", "Candeggina"),
        ("Nitrato de amonio", "Nitrato di ammonio"),
        ("Urea", "Urea"),
        ("Benceno", "Benzene"),
        ("Síntesis de NH₃", "Sintesi di NH₃"),
        ("Prueba con cal apagada", "Prova con acqua di calce"),
        ("Corrosión / óxido", "Ruggine"),
        ("Respiración", "Respirazione"),
        ("Fotosíntesis", "Fotosintesi"),
        ("Área superficial del prisma rectangular", "Superficie del prisma rettangolare"),
        ("Distancia 3D", "Distanza 3D"),
        ("Área superficial de la esfera", "Superficie della sfera"),
        ("Sector circular", "Settore circolare"),
        ("Trapecio", "Trapezio"),
        ("Punto medio", "Punto medio"),
        ("Punto–pendiente", "Punto-pendenza"),
        ("Distancia", "Distanza"),
        ("Pendiente m", "Pendenza m"),
        ("Diferencia de cuadrados", "Differenza di quadrati"),
        ("Fórmula cuadrática", "Formula quadratica"),
        ("Sucesiones · combinatoria y estadística", "Successioni · combinatoria · statistica"),
        ("Trigonometría · identidades", "Trigonometria · identità"),
        ("Geometría · área y volumen", "Geometria · area e volume"),
        ("Álgebra · coordenadas y recta", "Algebra · coordinate e retta"),
        ("Iones · sales · ácidos", "Ioni · sali · acidi"),
        ("Moléculas · estados · reacciones", "Molecole · stati · reazioni"),
        ("Griego · sumas y cálculo", "Greco · somme e calcolo"),
        ("Trig · logaritmos y exponencial", "Trig · log ed exp"),
        ("Álgebra · fracciones y raíces", "Algebra · frazioni e radici"),
        ("Básico · números y comparación", "Base · numeri e confronto"),
        ("Fórmulas químicas K–12", "Formule chimiche K–12"),
        ("Ecuaciones K–12", "Equazioni K–12"),
        ("Matemáticas K–12", "Matematica K–12"),
        ("Cargando editor de matemáticas…", "Caricamento editor matematico…"),
        ("Insertar ecuación", "Inserisci equazione"),
        ("Inserte matemáticas en línea ($...$) en el cursor, o añádalas al nodo seleccionado si no está editando",
         "Inserisci matematica in linea ($...$) al cursore, o accoda al nodo selezionato se non stai modificando"),
        ("Elija el color del marcador resaltador", "Scegli il colore dell’evidenziatore"),
        ("Dibuje en el lienzo como un marcador; se borra al salir de la presentación",
         "Disegna sull’area di disegno come evidenziatore; si cancella uscendo dalla presentazione"),
        ("Marcador resaltador", "Evidenziatore"),
        ("Salir de pantalla completa", "Esci da schermo intero"),
        ("Nodo de efecto añadido", "Nodo effetto aggiunto"),
        ("Dirección", "Direzione"),
        ("Par de diferencias añadido", "Coppia di differenze aggiunta"),
        ("Diferencia B{n}", "Differenza B{n}"),
        ("Diferencia A{n}", "Differenza A{n}"),
        ("Eliminados {count} nodo(s)", "Eliminati {count} nodo/i"),
        ("Eliminados {count} atributo(s)", "Eliminati {count} attributo/i"),
        ("Eliminados {count} par(es) analógico(s)", "Eliminate {count} coppie analogiche"),
        ("Eliminar", "Elimina"),
        ("Eliminar nodos", "Elimina nodi"),
        ("Eliminar nodo", "Elimina nodo"),
        ("Eliminar atributo", "Elimina attributo"),
        ("Eliminar par analógico", "Elimina coppia analogica"),
        ("Cree primero un diagrama", "Crea prima un diagramma"),
        ("Los modos del mapa conceptual están en desarrollo",
         "Le modalità della mappa concettuale sono in sviluppo"),
        ("Generación de conceptos", "Generazione concetti"),
        ("Solo el propietario del diagrama puede usar la generación con IA durante la colaboración",
         "Solo il proprietario del diagramma può usare la generazione IA durante la collaborazione"),
        ("Hijo añadido", "Figlio aggiunto"),
        ("Nodo de causa añadido", "Nodo causa aggiunto"),
        ("No se puede generar", "Impossibile generare"),
        ("No se puede eliminar el nodo o nodos seleccionados",
         "Impossibile eliminare i nodi selezionati"),
        ("No se puede eliminar el nodo de evento", "Impossibile eliminare il nodo evento"),
        ("No se puede eliminar la etiqueta de dimensión",
         "Impossibile eliminare l’etichetta di dimensione"),
        ("No se puede añadir un elemento secundario", "Impossibile aggiungere un figlio"),
        ("Rama añadida", "Ramo aggiunto"),
        ("Grosor", "Spessore"),
        ("Borde", "Bordo"),
        ("Fondo", "Sfondo"),
        ("Color de fondo", "Colore di sfondo"),
        ("Atributo añadido", "Attributo aggiunto"),
        ("Aplicado", "Applicato"),
        ("Par analógico añadido", "Coppia analogica aggiunta"),
        ("Alinear", "Allinea"),
        ("Generando…", "Generazione in corso…"),
        ("Generar con IA", "Genera con IA"),
        ("Añadir subpaso", "Aggiungi sottopasso"),
        ("Añadir paso", "Aggiungi passaggio"),
        ("Añadir", "Aggiungi"),
        ("Añadir par", "Aggiungi coppia"),
        ("La función «Añadir nodo» está en desarrollo", "Aggiungi nodo è in sviluppo"),
        ("Añadir nodo", "Aggiungi nodo"),
        ("Añadir efecto", "Aggiungi effetto"),
        ("Añadir causa", "Aggiungi causa"),
        ("Añadir atributo", "Aggiungi attributo"),
        ("Añadir par analógico", "Aggiungi coppia analogica"),
        ("No se puede restablecer: seleccione primero un tipo de diagrama",
         "Impossibile reimpostare: scegli prima un tipo di diagramma"),
        ("Restablecer valores predeterminados", "Ripristina predefiniti"),
        ("Restablecer", "Reimposta"),
        (
            "Se perderá todo el contenido actual, incluido el diagrama y la paleta de nodos. "
            "Esta acción no se puede deshacer.",
            (
                "Perderai tutto il contenuto attuale, inclusi diagramma e tavolozza dei nodi. "
                "Azione irreversibile."
            ),
        ),
        ("No se pudo analizar el archivo del diagrama; inténtelo de nuevo",
         "Impossibile analizzare il file del diagramma, riprova"),
        ("Archivo de diagrama no válido. Elija un archivo MG exportado desde MindGraph.",
         "File diagramma non valido. Seleziona un file MG esportato da MindGraph."),
        ("Formato de exportación desconocido: {format}", "Formato di esportazione sconosciuto: {format}"),
        ("Error al exportar el SVG; inténtelo de nuevo", "Esportazione SVG non riuscita, riprova"),
        ("SVG exportado correctamente", "SVG esportato correttamente"),
        ("Error al exportar el PNG; inténtelo de nuevo", "Esportazione PNG non riuscita, riprova"),
        ("PNG exportado correctamente", "PNG esportato correttamente"),
        ("Error al exportar el PDF; inténtelo de nuevo", "Esportazione PDF non riuscita, riprova"),
        ("PDF exportado correctamente", "PDF esportato correttamente"),
        ("No hay datos del diagrama para exportar", "Nessun dato del diagramma da esportare"),
        ("Archivo MG exportado correctamente", "File MG esportato correttamente"),
        ("Error al exportar el archivo MG; inténtelo de nuevo", "Esportazione file MG non riuscita, riprova"),
        ("No se puede exportar: el lienzo no está pronto",
         "Impossibile esportare: l’area di disegno non è pronta"),
        ("Nueva subparte", "Nuova sottoparte"),
        ("concepto raíz", "concetto radice"),
        ("Intro", "Invio"),
        ("Otras posibles dimensiones de descomposición para este tema:",
         "Altre possibili dimensioni di scomposizione per questo tema:"),
        ("Otros posibles patrones analógicos para este tema:",
         "Altri possibili schemi analogici per questo tema:"),
        ("Otras posibles dimensiones de clasificación para este tema:",
         "Altre possibili dimensioni di classificazione per questo tema:"),
        ("Salir de pantalla completa", "Esci da schermo intero"),
        ("Ajustar al lienzo", "Adatta area di disegno"),
        ("Pantalla completa", "Schermo intero"),
        ("Mostrar herramientas de presentación", "Mostra strumenti presentazione"),
        ("Ocultar herramientas de presentación", "Nascondi strumenti presentazione"),
        ("Colaboración", "Collaborazione"),
        ("Unidos: {title}", "Partecipazione: {title}"),
        ("Presentación unida: {title}", "Presentazione: {title}"),
        ("Unirse", "Entra"),
        ("Importar", "Importa"),
        ("Colaborar", "Collabora"),
        ("Cancelar", "Annulla"),
        ("Exportar", "Esporta"),
        ("Atrás", "Indietro"),
        ("Deshacer", "Annulla"),
        ("Rehacer", "Ripeti"),
        ("Texto", "Testo"),
        ("Estilo", "Stile"),
        ("Estilo aplicado", "Stile applicato"),
        ("Paso añadido", "Passaggio aggiunto"),
        ("Similitud {n}", "Somiglianza {n}"),
        ("Opacidad", "Opacità"),
        ("Insertar", "Inserisci"),
        ("Cancelar", "Annulla"),
        ("Seleccione primero un nodo", "Seleziona prima un nodo"),
        ("Química", "Chimica"),
        ("Español", "Spagnolo"),
        ("Función «Añadir nodo» próximamente", "Aggiungi nodo in arrivo"),
        ("Pegar", "Incolla"),
        ("Copiar", "Copia"),
        ("Editar", "Modifica"),
        ("Concepto nuevo", "Nuovo concetto"),
        ("Clasificación por", "Classificazione per"),
        ("Descomposición por", "Scomposizione per"),
        ("Introduzca texto…", "Inserisci testo…"),
        ("Respuestas:", "Risposte:"),
        ("se relaciona con", "è in relazione con"),
        ("Sub-elemento", "Sotto-elemento"),
        ("Nueva similitud", "Nuova somiglianza"),
        ("Diferencia derecha", "Differenza a destra"),
        ("Diferencia izquierda", "Differenza a sinistra"),
        ("Nuevo elemento", "Nuovo elemento"),
        ("Nuevo efecto", "Nuovo effetto"),
        ("Nuevo contexto", "Nuovo contesto"),
        ("Nuevo concepto", "Nuovo concetto"),
        ("Nuevo hijo", "Nuovo figlio"),
        ("Nueva causa", "Nuova causa"),
        ("Nueva categoría", "Nuova categoria"),
        ("Nueva derecha", "Nuovo a destra"),
        ("Nueva izquierda", "Nuovo a sinistra"),
        ("Nueva rama", "Nuovo ramo"),
        ("Nuevo atributo", "Nuovo attributo"),
        ("Relación analógica:", "Relazione analogica:"),
        ("Relación", "Relazione"),
        ("Evento principal", "Evento principale"),
        ("Tema central", "Tema centrale"),
        ("Categoría {n}", "Categoria {n}"),
        ("Causa {n}", "Causa {n}"),
        ("Efecto {n}", "Effetto {n}"),
        ("Tema raíz", "Tema radice"),
        ("Proceso", "Processo"),
        ("Parte {n}", "Parte {n}"),
        ("Elemento {n}.{m}", "Elemento {n}.{m}"),
        ("Contexto {n}", "Contesto {n}"),
        ("Hijo {n}.{m}", "Figlio {n}.{m}"),
        ("Tema", "Tema"),
        ("Tema A", "Tema A"),
        ("Tema B", "Tema B"),
        ("Atributo {n}", "Attributo {n}"),
        ("Rama {n}", "Ramo {n}"),
        ("Elemento A{n}", "Elemento A{n}"),
        ("Elemento B{n}", "Elemento B{n}"),
        ("Subparte {n}.{m}", "Sottoparte {n}.{m}"),
        ("Subpaso {n}.{m}", "Sottopasso {n}.{m}"),
        ("Paso {n}", "Passaggio {n}"),
        ("Guardando…", "Salvataggio in corso…"),
        ("Cambios sin guardar", "Modifiche non salvate"),
        ("Guardado", "Salvato"),
        ("{n} en línea", "{n} in linea"),
    ]
    out = value
    for src, tgt in sorted(pairs, key=lambda x: -len(x[0])):
        out = out.replace(src, tgt)
    return out


def emit_it() -> None:
    nl_text = NL.read_text(encoding="utf-8")
    rows = nl_key_multiline_rows(nl_text)
    es_vals = parse_values_ordered(ES)
    if len(rows) != len(es_vals):
        raise SystemExit(f"row {len(rows)} vs es {len(es_vals)}")
    it_vals = [spanish_to_italian(v) for v in es_vals]
    out_lines = [
        "/**",
        " * it UI — canvas",
        " */",
        "",
        "export default {",
    ]
    for (key, multiline), val in zip(rows, it_vals, strict=True):
        esc = encode_ts_single_quoted(val)
        if multiline:
            out_lines.append(f"  '{key}':")
            out_lines.append(f"    '{esc}',")
        else:
            out_lines.append(f"  '{key}': '{esc}',")
    out_lines.append("}")
    out_lines.append("")
    OUT_IT.write_text("\n".join(out_lines), encoding="utf-8")
    print("Wrote", OUT_IT.relative_to(ROOT.parent))


if __name__ == "__main__":
    emit_it()
