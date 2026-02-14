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
        Schema::table('execution_logs', function (Blueprint $table) {
            $table->text('screenshot_url')->nullable()->after('screenshot_path');
            $table->bigInteger('screenshot_size')->nullable()->after('screenshot_url');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('execution_logs', function (Blueprint $table) {
            $table->dropColumn(['screenshot_url', 'screenshot_size']);
        });
    }
};
