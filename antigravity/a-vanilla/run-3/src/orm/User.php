<?php

use Tina4\ORM;

class User extends ORM
{
    public string $tableName = "users";
    public string $primaryKey = "id";
    public bool $autoMap = true;

    public int $id;
    public string $name;
    public string $email;
    public string $passwordHash;
    public string $createdAt;

    /**
     * Hash a password
     */
    public static function hashPassword(string $password): string
    {
        return password_hash($password, PASSWORD_DEFAULT);
    }

    /**
     * Verify a password against the stored hash
     */
    public function verifyPassword(string $password): bool
    {
        return password_verify($password, $this->passwordHash);
    }

    /**
     * Convert to safe dict excluding the password hash
     */
    public function toSafeDict(): array
    {
        $dict = $this->toDict();
        unset($dict["passwordHash"]);
        unset($dict["password_hash"]);
        return $dict;
    }
}
