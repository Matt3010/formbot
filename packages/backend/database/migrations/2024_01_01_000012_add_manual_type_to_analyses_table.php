<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Add 'manual' to the type enum (PostgreSQL-only constraint, skip for SQLite)
        if (DB::connection()->getDriverName() === 'pgsql') {
            DB::statement("ALTER TABLE analyses DROP CONSTRAINT IF EXISTS analyses_type_check");
            DB::statement("ALTER TABLE analyses ADD CONSTRAINT analyses_type_check CHECK (type::text = ANY (ARRAY['simple'::text, 'login_and_target'::text, 'next_page'::text, 'manual'::text]))");
        }
    }

    public function down(): void
    {
        if (DB::connection()->getDriverName() === 'pgsql') {
            DB::statement("ALTER TABLE analyses DROP CONSTRAINT IF EXISTS analyses_type_check");
            DB::statement("ALTER TABLE analyses ADD CONSTRAINT analyses_type_check CHECK (type::text = ANY (ARRAY['simple'::text, 'login_and_target'::text, 'next_page'::text]))");
        }
    }
};
