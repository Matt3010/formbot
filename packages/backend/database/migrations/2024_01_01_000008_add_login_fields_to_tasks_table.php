<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('tasks', function (Blueprint $table) {
            $table->boolean('requires_login')->default(false);
            $table->text('login_url')->nullable();
            $table->boolean('login_every_time')->default(true);
            $table->text('login_session_data')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('tasks', function (Blueprint $table) {
            $table->dropColumn(['requires_login', 'login_url', 'login_every_time', 'login_session_data']);
        });
    }
};
