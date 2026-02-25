<?php
require 'config.php';
try {
    $pdo->exec('ALTER TABLE transcriptions ADD COLUMN temp_refinado_srt LONGTEXT AFTER whisper_srt');
    echo "Columna creada con éxito.";
} catch (Exception $e) {
    if (strpos($e->getMessage(), 'Duplicate column name') !== false) {
        echo "La columna ya existe.";
    } else {
        echo "Error: " . $e->getMessage();
    }
}
?>