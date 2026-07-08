<?php

use Tina4\ORM;

class Loan extends ORM
{
    public string $tableName = "loans";
    public string $primaryKey = "id";
    public bool $autoMap = true;

    public int $id;
    public int $bookId;
    public int $memberId;
    public string $borrowDate;
    public string $dueDate;
    public ?string $returnedDate = null;
    public string $createdAt;
    public string $updatedAt;

    /**
     * Get the book borrowed in this loan
     * @return Book|null
     */
    public function book(): ?Book
    {
        return $this->belongsTo(Book::class, "book_id");
    }

    /**
     * Get the member who made this loan
     * @return Member|null
     */
    public function member(): ?Member
    {
        return $this->belongsTo(Member::class, "member_id");
    }
}
