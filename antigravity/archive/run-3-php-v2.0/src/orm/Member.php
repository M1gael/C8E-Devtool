<?php

use Tina4\ORM;

class Member extends ORM
{
    public string $tableName = "members";
    public string $primaryKey = "id";
    public bool $autoMap = true;

    public int $id;
    public string $name;
    public string $email;
    public string $joinDate;
    public string $createdAt;
    public string $updatedAt;

    /**
     * Get borrowing history for this member
     * @return Loan[]
     */
    public function loans(): array
    {
        return $this->hasMany(Loan::class, "member_id");
    }
}
