<?php
// PHPUnit bootstrap for Tina4

require_once __DIR__ . '/../vendor/autoload.php';

$testDbFile = __DIR__ . '/../data/test.db';
if (file_exists($testDbFile)) {
    unlink($testDbFile);
}

// Force test environment DB config
$_ENV["TINA4_DATABASE_URL"] = "sqlite:///c:/Users/work/Documents/projects/C8E-Devtool/antigravity/a-vanilla/run-3/data/test.db";
putenv("TINA4_DATABASE_URL=sqlite:///c:/Users/work/Documents/projects/C8E-Devtool/antigravity/a-vanilla/run-3/data/test.db");

// Load ORM models manually (PSR-4 autoloading requires namespaces)
foreach (glob(__DIR__ . '/../src/orm/*.php') as $filename) {
    require_once $filename;
}

// Initialize the Tina4 application (boots ORM, registers routes, runs migrations)
$app = new \Tina4\App();
$app->start();
