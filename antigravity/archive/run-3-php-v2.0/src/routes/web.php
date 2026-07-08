<?php

use Tina4\Router;
use Tina4\Database\Database;
use Tina4\I18n;

/**
 * Resolves the language code from request params, session, or defaults to English
 */
function resolveWebLanguage($request): string
{
    $lang = $request->queryParam("lang");
    if (!empty($lang)) {
        $lang = strtolower(trim($lang));
        if (in_array($lang, ["en", "es"])) {
            $request->session->set("lang", $lang);
            return $lang;
        }
    }

    $sessionLang = $request->session->get("lang");
    if (!empty($sessionLang)) {
        return $sessionLang;
    }

    return "en";
}

/**
 * Public catalog index page
 * @noauth
 */
Router::get("/", function ($request, $response) {
    $lang = resolveWebLanguage($request);
    $t = new I18n("src/locales", defaultLocale: "en");
    $t->setLocale($lang);

    $search = $request->queryParam("search", "");
    $page = (int) $request->queryParam("page", 1);
    $limit = 12;
    if ($page < 1) $page = 1;
    $offset = ($page - 1) * $limit;

    $bookModel = new Book();
    $books = [];
    $totalCount = 0;

    if (!empty($search)) {
        $books = $bookModel->select("SELECT * FROM books WHERE (title LIKE :search OR author LIKE :search OR published_year LIKE :search OR isbn LIKE :search) ORDER BY title ASC", ["search" => "%" . $search . "%"], $limit, $offset);
        $totalCount = $bookModel->count("(title LIKE :search OR author LIKE :search OR published_year LIKE :search OR isbn LIKE :search)", ["search" => "%" . $search . "%"]);
    } else {
        $books = $bookModel->select("SELECT * FROM books ORDER BY title ASC", [], $limit, $offset);
        $totalCount = $bookModel->count();
    }

    $records = [];
    foreach ($books as $b) {
        $dict = $b->toDict();
        $dict["available"] = $b->isAvailable();
        $records[] = $dict;
    }

    $totalPages = ceil($totalCount / $limit);
    if ($totalPages < 1) $totalPages = 1;

    // Get current user if logged in
    $user = $request->session->get("user");

    return $response->render("home.twig", [
        "t" => $t,
        "active_lang" => $lang,
        "books" => $records,
        "search" => $search,
        "current_page" => $page,
        "total_pages" => $totalPages,
        "user" => $user,
        "page" => "catalogue"
    ]);
});

/**
 * Public book details page
 * @noauth
 */
Router::get("/book/{id:int}", function ($request, $response) {
    $lang = resolveWebLanguage($request);
    $t = new I18n("src/locales", defaultLocale: "en");
    $t->setLocale($lang);

    $id = $request->params["id"];

    $book = new Book();
    $book->load("id = ?", [$id]);

    if (empty($book->id)) {
        return $response->redirect("/?error=not_found");
    }

    $db = Database::getConnection();
    // Fetch loan history with member names
    $loansSql = "SELECT l.borrow_date, l.due_date, l.returned_date, m.name as member_name 
                 FROM loans l 
                 JOIN members m ON l.member_id = m.id 
                 WHERE l.book_id = :book_id 
                 ORDER BY l.borrow_date DESC";
    $loans = $db->fetch($loansSql, ["book_id" => $id]);

    $bookData = $book->toDict();
    $bookData["available"] = $book->isAvailable();
    $bookData["loans"] = $loans;

    $user = $request->session->get("user");

    return $response->render("book.twig", [
        "t" => $t,
        "active_lang" => $lang,
        "book" => $bookData,
        "user" => $user
    ]);
});

/**
 * Staff login page
 * @noauth
 */
Router::get("/login", function ($request, $response) {
    $lang = resolveWebLanguage($request);
    $t = new I18n("src/locales", defaultLocale: "en");
    $t->setLocale($lang);

    // If already logged in, redirect to dashboard
    $user = $request->session->get("user");
    if ($user !== null) {
        return $response->redirect("/dashboard");
    }

    $error = $request->queryParam("error", "");
    $message = $request->queryParam("message", "");
    
    $logoutMessage = "";
    if ($message === "logged_out") {
        $logoutMessage = $lang === "es" ? "Sesión cerrada correctamente." : "Signed out successfully.";
    }

    return $response->render("login.twig", [
        "t" => $t,
        "active_lang" => $lang,
        "error" => $error,
        "logout_message" => $logoutMessage
    ]);
});

/**
 * Staff dashboard page
 * @noauth
 */
Router::get("/dashboard", function ($request, $response) {
    $lang = resolveWebLanguage($request);
    $t = new I18n("src/locales", defaultLocale: "en");
    $t->setLocale($lang);

    $staff = $request->user;

    // Fetch books
    $bookModel = new Book();
    $allBooks = $bookModel->select("SELECT * FROM books ORDER BY title ASC", [], 10000);
    $booksData = [];
    foreach ($allBooks as $b) {
        $dict = $b->toDict();
        $dict["available"] = $b->isAvailable();
        $booksData[] = $dict;
    }

    // Fetch members
    $memberModel = new Member();
    $members = $memberModel->select("SELECT * FROM members ORDER BY name ASC", [], 10000);
    $membersData = array_map(fn($m) => $m->toDict(), $members);

    // Fetch audit logs
    $db = Database::getConnection();
    $logsSql = "SELECT a.*, u.name as staff_name, u.email as staff_email 
                FROM activity_logs a 
                JOIN users u ON a.user_id = u.id 
                ORDER BY a.created_at DESC LIMIT 100";
    $logs = $db->fetch($logsSql);

    return $response->render("dashboard.twig", [
        "t" => $t,
        "active_lang" => $lang,
        "user" => $staff,
        "all_books" => $booksData,
        "members" => $membersData,
        "audit_logs" => $logs,
        "page" => "dashboard"
    ]);
}, ["authMiddleware"]);
