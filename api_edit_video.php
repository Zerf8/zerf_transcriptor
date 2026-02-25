<?php
require 'config.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST' && $_SERVER['REQUEST_METHOD'] !== 'PUT') {
    http_response_code(405);
    echo json_encode(['status' => 'error', 'detail' => 'Method Not Allowed']);
    exit;
}

$id = $_GET['id'] ?? null;
if (!$id) {
    http_response_code(400);
    echo json_encode(['status' => 'error', 'detail' => 'Missing YouTube ID']);
    exit;
}

// Ensure the request has JSON body
$json = file_get_contents('php://input');
$data = json_decode($json, true);

if (!$data) {
    http_response_code(400);
    echo json_encode(['status' => 'error', 'detail' => 'Invalid JSON payload']);
    exit;
}

try {
    // We update fields that are present in the payload
    $fields = [];
    $params = [':youtube_id' => $id];

    $allowedFields = ['title', 'description', 'tags', 'category', 'channel', 'duration_string', 'thumbnail'];

    foreach ($allowedFields as $field) {
        if (isset($data[$field])) {
            $fields[] = "$field = :$field";
            $params[":$field"] = $data[$field];
        }
    }

    if (empty($fields)) {
        echo json_encode(['status' => 'success', 'message' => 'No fields to update']);
        exit;
    }

    $sql = "UPDATE videos SET " . implode(', ', $fields) . ", updated_at = NOW() WHERE youtube_id = :youtube_id";

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);

    echo json_encode(['status' => 'success', 'message' => 'Video actualizado correctamente']);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'detail' => $e->getMessage()]);
}
?>