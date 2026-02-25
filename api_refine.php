<?php
require 'config.php';

header('Content-Type: application/json');

$id = $_GET['v'] ?? null;
if (!$id) {
    echo json_encode(['error' => 'Falta ID de video']);
    exit;
}

// 1. Cargar el Diccionario
$diccionarioPath = __DIR__ . '/data/diccionario.json';
$diccionario = [];
if (file_exists($diccionarioPath)) {
    $diccionario = json_decode(file_get_contents($diccionarioPath), true);
}
$correcciones = json_encode($diccionario['correcciones_aprendidas'] ?? []);

// 2. Obtener la transcripción original (VTT o SRT)
try {
    $stmt = $pdo->prepare("
        SELECT t.whisper_srt, t.vtt 
        FROM transcriptions t 
        JOIN videos v ON t.video_id = v.id 
        WHERE v.youtube_id = :id
    ");
    $stmt->execute([':id' => $id]);
    $row = $stmt->fetch();
    
    if (!$row) {
        echo json_encode(['error' => 'No se encontró transcripción']);
        exit;
    }

    $source_text = $row['vtt'] ?: $row['whisper_srt'];
    
    // 3. Parsear bloques (Formato simplificado para la IA)
    // Dividimos por bloques de tiempo.
    // Usaremos una expresión regular para capturar el índice, tiempos y texto.
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
    exit;
}

// 4. Llamar a Gemini (Simulado o Directo por CURL)
// Para que sea eficiente y no tarde 1 minuto, pediremos a Gemini que procese 
// el texto completo pero respetando la estructura de bloques que le daremos.

$apiKey = $env['GOOGLE_API_KEY'] ?? '';
if (!$apiKey) {
    echo json_encode(['error' => 'Falta API Key']);
    exit;
}

function callGemini($prompt, $apiKey) {
    $url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" . $apiKey;
    
    $data = [
        "contents" => [
            [
                "parts" => [
                    ["text" => $prompt]
                ]
            ]
        ]
    ];

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    if (curl_errno($ch)) {
        return ['error' => curl_error($ch)];
    }
    curl_close($ch);
    
    return json_decode($response, true);
}

// 4. Preparar el Prompt
$prompt = "Eres el editor jefe de 'ZerfAnalitza'. Tu misión es limpiar y dar formato profesional a esta transcripción.
        
REGLAS:
1. Usa el diccionario de correcciones: $correcciones
2. SIEMPRE mantén el estilo del 'Barbut' (coloquial, apasionado, culé). 
3. SALUDO OBLIGATORIO: Empieza el bloque [1] con 'Hola Culerada, Hola Zerfistas. A ver...'.
4. Formato de respuesta: Devuelve CADA BLOQUE con su índice entre corchetes, por ejemplo:
[1]: Hola Culerada, Hola Zerfistas...
[2]: El partido de hoy contra el...
[3]: ...

IMPORTANTE: No añadas explicaciones, solo los bloques refinados. Mantén el mismo número de bloques que el original.

TRANSCRIPCIÓN ORIGINAL:
";

// Añadimos solo una parte de la transcripción para no exceder límites de token si es muy larga
// En un entorno real, procesaríamos por bloques, pero para este test enviamos lo principal.
$prompt .= substr($source_text, 0, 10000);

// 5. Llamar a Gemini
$geminiResponse = callGemini($prompt, $apiKey);

if (isset($geminiResponse['error'])) {
    echo json_encode(['error' => 'Error API Gemini: ' . json_encode($geminiResponse['error'])]);
    exit;
}

$refinedText = $geminiResponse['candidates'][0]['content']['parts'][0]['text'] ?? '';

if (!$refinedText) {
    echo json_encode([
        'error' => 'Gemini no devolvió texto',
        'debug' => $geminiResponse
    ]);
    exit;
}

echo json_encode([
    'youtube_id' => $id,
    'refined_raw' => $refinedText
]);
