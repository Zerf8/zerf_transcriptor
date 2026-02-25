<?php
require 'config.php';
try {
    $gemini = $pdo->query("SELECT COUNT(*) FROM transcriptions WHERE gemini_text IS NOT NULL AND TRIM(gemini_text) != ''")->fetchColumn();
    $whisper = $pdo->query("SELECT COUNT(*) FROM transcriptions WHERE whisper_text IS NOT NULL AND TRIM(whisper_text) != ''")->fetchColumn();
    $raw = $pdo->query("SELECT COUNT(*) FROM transcriptions WHERE raw_json IS NOT NULL AND TRIM(raw_json) != ''")->fetchColumn();

    echo "gemini: $gemini\n";
    echo "whisper: $whisper\n";
    echo "raw: $raw\n";

    // Let's also check if maybe the DB_NAME was different in python. Python uses os.getenv("DB_NAME").
    // Let's print the actual DB we connected to.
    $dbName = $pdo->query("SELECT DATABASE()")->fetchColumn();
    echo "Connected to DB: $dbName\n";
} catch (Exception $e) {
    echo "Error: " . $e->getMessage();
}
