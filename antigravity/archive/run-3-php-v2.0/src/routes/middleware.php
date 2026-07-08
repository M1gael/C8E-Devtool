<?php

use Tina4\Auth;

/**
 * Auth Middleware to protect library staff operations
 */
function authMiddleware($request, $response)
{
    $token = null;

    // 1. Check Authorization header
    $authHeader = $request->header("Authorization") ?? "";
    if (str_starts_with($authHeader, "Bearer ")) {
        $token = substr($authHeader, 7);
    }

    // 2. Check Cookie
    if (empty($token) && isset($request->cookies["token"])) {
        $token = $request->cookies["token"];
    }

    // 3. Check Session
    $sessionUser = $request->session->get("user");

    $userPayload = null;
    if (!empty($token)) {
        $userPayload = Auth::validToken($token);
    }

    if ($userPayload !== null) {
        $request->user = $userPayload;
    } elseif ($sessionUser !== null) {
        $request->user = $sessionUser;
    } else {
        // Not authorized!
        // Determine if it is an API route or a web page
        if (str_starts_with($request->path, "/api/")) {
            return $response->json(["error" => "Unauthorized: Staff sign in required"], 401);
        } else {
            return $response->redirect("/login?error=unauthorized");
        }
    }
}
