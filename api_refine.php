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

    if (!$row || (empty($row['whisper_srt']) && empty($row['vtt']))) {
        echo json_encode(['error' => 'No se encontró ninguna transcripción (VTT o Whisper)']);
        exit;
    }

    // PRIORIDAD AL VTT para mantener los tiempos cortos estilo Karaoke
    $source_text = !empty($row['vtt']) ? $row['vtt'] : $row['whisper_srt'];


    // 3. Parsear bloques para la IA
    $cleanText = preg_replace('/^WEBVTT\s+/i', '', $source_text);
    $cleanText = str_replace(["\r\n", "\r"], "\n", $cleanText);
    $rawBlocks = explode("\n\n", trim($cleanText));

    $parsedBlocks = [];
    $blockIndex = 1;

    foreach ($rawBlocks as $block) {
        $lines = array_filter(array_map('trim', explode("\n", $block)), function ($l) {
            return $l !== "";
        });
        if (count($lines) < 2)
            continue;

        $textLines = [];
        if (strpos($lines[0], '-->') !== false) {
            $textLines = array_slice($lines, 1);
        } else if (isset($lines[1]) && strpos($lines[1], '-->') !== false) {
            $textLines = array_slice($lines, 2);
        } else {
            continue;
        }

        if (!empty($textLines)) {
            $parsedBlocks[] = [
                'index' => $blockIndex++,
                'text' => implode(" ", $textLines)
            ];
        }
    }

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

function callGemini($prompt, $apiKey)
{
    $url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-pro-exp-02-05:generateContent?key=" . $apiKey;

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

// 5. Preparar el Prompt
$prompt = "Eres el editor jefe de 'ZerfAnalitza'. Tu misión es limpiar y dar formato profesional a esta transcripción manteniendo escrupulosamente los metadatos de audio y los tiempos.
        
REGLAS:
1. Usa el diccionario de correcciones: $correcciones
2. MANTÉN ESTRICTAMENTE EL MISMO NÚMERO DE BLOQUES. No unas bloques. Cada índice de bloque debe tener su texto correspondiente.
3. SIEMPRE mantén el estilo del 'Barbut' (coloquial, apasionado, culé). 
4. FORMATO: Responde ÚNICAMENTE con los bloques refinados. No inventes despedidas. Si un bloque parece una alucinación (como "suscríbete" repetido en silencio), límpialo pero NO elimines el bloque.
5. NO expliques nada, solo devuelve la lista de bloques.
EJEMPLO:
[1] Hola Culerada.
[2] Vaya partido el de hoy.
...

TRANSCRIPCIÓN ORIGINAL:
";

// Generar el texto estructurado por bloques para Gemini
$blocksText = "";
foreach ($parsedBlocks as $b) {
    $blocksText .= "[" . $b['index'] . "] " . $b['text'] . "\n";
}

// Por ahora limitamos los caracteres para evitar timeout/exceder límites, pero pasamos contenido estructurado
$prompt .= substr($blocksText, 0, 15000);

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
], JSON_UNESCAPED_UNICODE);
