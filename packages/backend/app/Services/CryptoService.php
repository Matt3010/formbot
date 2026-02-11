<?php

namespace App\Services;

use Illuminate\Support\Facades\Crypt;

class CryptoService
{
    /**
     * Encrypt a value using Laravel's encryption.
     */
    public function encrypt(string $value): string
    {
        return Crypt::encryptString($value);
    }

    /**
     * Decrypt a value using Laravel's encryption.
     */
    public function decrypt(string $value): string
    {
        return Crypt::decryptString($value);
    }
}
