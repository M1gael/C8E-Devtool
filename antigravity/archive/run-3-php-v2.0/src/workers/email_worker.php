<?php
require_once __DIR__ . '/../../vendor/autoload.php';

use Tina4\Queue;
use Tina4\Messenger;

// Initialize the environment if needed by starting App container context
// Tina4 autoloads env variables from .env
$queue = new Queue(topic: 'emails');

echo "Email queue worker started. Listening on topic: 'emails'...\n";

foreach ($queue->consume('emails') as $job) {
    $payload = $job->payload;
    echo "[" . date("c") . "] Processing job ID: {$job->id} to {$payload['to']}...\n";

    try {
        $mailer = new Messenger();
        $htmlBody = "
            <html>
            <body style='font-family: Arial, sans-serif; padding: 20px;'>
                <h2>Lend Library - Borrowing Receipt</h2>
                <p>Hello <strong>{$payload['name']}</strong>,</p>
                <p>You have successfully borrowed: <strong>{$payload['title']}</strong>.</p>
                <p><strong>Borrow Date:</strong> {$payload['borrow_date']}</p>
                <p><strong>Due Date:</strong> <span style='color: #d9534f; font-weight: bold;'>{$payload['due_date']}</span></p>
                <p>Please return the book by the due date. Thank you!</p>
            </body>
            </html>
        ";

        $textBody = "Lend Library - Borrowing Receipt\n\n" .
                    "Hello {$payload['name']},\n\n" .
                    "You have successfully borrowed: {$payload['title']}.\n" .
                    "Borrow Date: {$payload['borrow_date']}\n" .
                    "Due Date: {$payload['due_date']}\n\n" .
                    "Please return the book by the due date. Thank you!";

        $result = $mailer->send(
            $payload['to'],
            "Book Borrowed: {$payload['title']}",
            $htmlBody,
            ["text_body" => $textBody]
        );

        if ($result["success"]) {
            echo "  Email sent successfully!\n";
            $job->complete();
        } else {
            echo "  Failed sending email: {$result['error']}\n";
            $job->fail($result['error']);
        }
    } catch (\Throwable $e) {
        echo "  Exception: {$e->getMessage()}\n";
        $job->fail($e->getMessage());
    }
}
