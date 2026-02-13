<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::table('form_definitions', function (Blueprint $table) {
            $table->boolean('human_breakpoint')->default(false)->after('two_factor_expected');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('form_definitions', function (Blueprint $table) {
            $table->dropColumn('human_breakpoint');
        });
    }
};
