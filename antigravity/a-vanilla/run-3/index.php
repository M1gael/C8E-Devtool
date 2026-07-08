<?php
require_once __DIR__ . '/vendor/autoload.php';

// Load ORM models manually (PSR-4 autoloading requires namespaces)
foreach (glob(__DIR__ . '/src/orm/*.php') as $filename) {
    require_once $filename;
}

$app = new \Tina4\App();

// Local development (fastest — built-in socket server with WebSocket support):
//   tina4 serve
//
// Production behind Apache/nginx (see .htaccess or nginx.conf.example):
//   Apache: mod_rewrite routes all requests through this file
//   nginx:  try_files $uri $uri/ /index.php?$query_string
//
// handle() detects the environment automatically:
//   - CLI (tina4 serve): bootstraps routes, server handles dispatch
//   - Apache/nginx/php-fpm: dispatches the current request and outputs response
$app->handle();
