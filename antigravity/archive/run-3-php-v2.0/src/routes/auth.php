<?php

use Tina4\Router;
use Tina4\Auth;

/**
 * @noauth
 */
Router::post("/api/auth/login", function ($request, $response) {
    $body = $request->body;

    if (empty($body["email"]) || empty($body["password"])) {
        return $response->json(["error" => "Email and password are required"], 400);
    }

    $email = trim($body["email"]);
    $password = $body["password"];

    $userModel = new User();
    $found = $userModel->select("SELECT * FROM users WHERE email = :email", ["email" => $email]);

    if (count($found) === 0) {
        return $response->json(["error" => "Invalid email or password"], 401);
    }

    /** @var User $user */
    $user = $found[0];

    if (!$user->verifyPassword($password)) {
        return $response->json(["error" => "Invalid email or password"], 401);
    }

    // Generate JWT token (expires in 24 hours)
    $token = Auth::getToken([
        "user_id" => $user->id,
        "email" => $user->email,
        "name" => $user->name
    ]);

    // Store user data in session
    $request->session->set("user", [
        "user_id" => $user->id,
        "email" => $user->email,
        "name" => $user->name
    ]);

    // Set cookie
    $response->cookie("token", $token, [
        "expires" => time() + (24 * 60 * 60), // 24 hours
        "path" => "/",
        "httponly" => true,
        "secure" => false, // false for HTTP localhost
        "samesite" => "Lax"
    ]);

    return $response->json([
        "message" => "Sign in successful",
        "token" => $token,
        "user" => $user->toSafeDict()
    ]);
});

/**
 * Handles web-based sign out
 * @noauth
 */
Router::get("/logout", function ($request, $response) {
    // Clear session
    $request->session->clear();
    $request->session->destroy();

    // Clear cookie
    $response->cookie("token", "", [
        "expires" => time() - 3600,
        "path" => "/"
    ]);

    return $response->redirect("/login?message=logged_out");
});

/**
 * Handles API-based sign out
 * @noauth
 */
Router::post("/api/auth/logout", function ($request, $response) {
    $request->session->clear();
    $request->session->destroy();

    $response->cookie("token", "", [
        "expires" => time() - 3600,
        "path" => "/"
    ]);

    return $response->json(["message" => "Sign out successful"]);
});
