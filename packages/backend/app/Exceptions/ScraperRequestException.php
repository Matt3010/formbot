<?php

namespace App\Exceptions;

use RuntimeException;

class ScraperRequestException extends RuntimeException
{
    public function __construct(
        string $message,
        private readonly int $statusCode = 500
    ) {
        parent::__construct($message);
    }

    public function statusCode(): int
    {
        return $this->statusCode;
    }
}
