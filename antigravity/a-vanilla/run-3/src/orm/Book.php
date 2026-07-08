<?php

use Tina4\ORM;

class Book extends ORM
{
    public string $tableName = "books";
    public string $primaryKey = "id";
    public bool $autoMap = true;

    public int $id;
    public string $title;
    public string $author;
    public int $publishedYear;
    public string $isbn;
    public ?string $coverImage = null;
    public string $createdAt;
    public string $updatedAt;

    /**
     * Get borrowing history for this book
     * @return Loan[]
     */
    public function loans(): array
    {
        return $this->hasMany(Loan::class, "book_id");
    }

    /**
     * Check if the book is currently available for borrowing
     * @return bool
     */
    public function isAvailable(): bool
    {
        // Search for active loans where returned_date is null
        $activeLoans = (new Loan())->where("book_id = ? AND (returned_date IS NULL OR returned_date = '')", [$this->id]);
        return count($activeLoans) === 0;
    }
}
