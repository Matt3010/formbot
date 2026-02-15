<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('analyses', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->text('url');
            $table->text('target_url')->nullable();
            $table->text('login_url')->nullable();
            // Keep initial enum values aligned with current app behavior for SQLite.
            // Later migrations still adjust PostgreSQL constraints for existing installs.
            $table->enum('type', ['simple', 'login_and_target', 'next_page', 'manual']);
            $table->enum('status', ['pending', 'analyzing', 'completed', 'failed', 'editing'])->default('pending');
            $table->jsonb('result')->nullable();
            $table->text('error')->nullable();
            $table->string('model', 100)->nullable();
            $table->uuid('task_id')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->timestamps();

            $table->index(['user_id', 'status']);
            $table->index('created_at');
            $table->foreign('task_id')->references('id')->on('tasks')->nullOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('analyses');
    }
};
