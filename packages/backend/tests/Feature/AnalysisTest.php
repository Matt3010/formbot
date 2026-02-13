<?php

namespace Tests\Feature;

use App\Models\Analysis;
use App\Models\Task;
use App\Models\User;
use App\Services\ScraperClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Laravel\Passport\Passport;
use Mockery;
use Tests\TestCase;

class AnalysisTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::create([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => bcrypt('password123'),
        ]);

        Passport::actingAs($this->user);
    }

    // -----------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------

    private function createAnalysis(array $overrides = []): Analysis
    {
        return Analysis::create(array_merge([
            'user_id' => $this->user->id,
            'url' => 'https://example.com/form',
            'type' => 'manual',
            'status' => 'completed',
            'model' => null,
        ], $overrides));
    }

    private function createOtherUser(): User
    {
        return User::create([
            'name' => 'Other User',
            'email' => 'other@example.com',
            'password' => bcrypt('password123'),
        ]);
    }

    // -----------------------------------------------------------------
    // GET /api/analyses — List analyses
    // -----------------------------------------------------------------

    public function test_list_analyses_returns_only_own_analyses(): void
    {
        $otherUser = $this->createOtherUser();

        // Create analyses for the authenticated user
        $this->createAnalysis(['url' => 'https://example.com/form1']);
        $this->createAnalysis(['url' => 'https://example.com/form2']);

        // Create an analysis for a different user
        Analysis::create([
            'user_id' => $otherUser->id,
            'url' => 'https://other.com/form',
            'type' => 'manual',
            'status' => 'completed',
            'model' => null,
        ]);

        $response = $this->getJson('/api/analyses');

        $response->assertStatus(200)
            ->assertJsonStructure([
                'data' => [
                    '*' => [
                        'id',
                        'user_id',
                        'url',
                        'target_url',
                        'login_url',
                        'type',
                        'status',
                        'result',
                        'error',
                        'model',
                        'task_id',
                        'started_at',
                        'completed_at',
                        'created_at',
                        'updated_at',
                    ],
                ],
                'links',
                'meta',
            ]);

        $this->assertCount(2, $response->json('data'));

        // Verify all returned analyses belong to the authenticated user
        foreach ($response->json('data') as $analysis) {
            $this->assertEquals($this->user->id, $analysis['user_id']);
        }
    }

    public function test_list_analyses_is_paginated(): void
    {
        // Create 30 analyses to exceed the default page size of 25
        for ($i = 0; $i < 30; $i++) {
            $this->createAnalysis(['url' => "https://example.com/form{$i}"]);
        }

        $response = $this->getJson('/api/analyses');

        $response->assertStatus(200);
        $this->assertCount(25, $response->json('data'));
        $this->assertEquals(30, $response->json('meta.total'));

        // Request page 2
        $responsePage2 = $this->getJson('/api/analyses?page=2');

        $responsePage2->assertStatus(200);
        $this->assertCount(5, $responsePage2->json('data'));
    }

    public function test_list_analyses_filters_by_status(): void
    {
        $this->createAnalysis(['status' => 'completed']);
        $this->createAnalysis(['status' => 'pending']);
        $this->createAnalysis(['status' => 'failed']);

        $response = $this->getJson('/api/analyses?status=completed');

        $response->assertStatus(200);
        $this->assertCount(1, $response->json('data'));
        $this->assertEquals('completed', $response->json('data.0.status'));
    }

    // -----------------------------------------------------------------
    // GET /api/analyses/{analysis} — Show analysis
    // -----------------------------------------------------------------

    public function test_show_own_analysis(): void
    {
        $analysis = $this->createAnalysis([
            'result' => ['forms' => [['selector' => '#my-form']]],
        ]);

        $response = $this->getJson("/api/analyses/{$analysis->id}");

        $response->assertStatus(200)
            ->assertJsonPath('data.id', $analysis->id)
            ->assertJsonPath('data.url', 'https://example.com/form')
            ->assertJsonPath('data.type', 'manual')
            ->assertJsonPath('data.status', 'completed')
            ->assertJsonStructure([
                'data' => [
                    'id',
                    'user_id',
                    'url',
                    'target_url',
                    'login_url',
                    'type',
                    'status',
                    'result',
                    'error',
                    'model',
                    'task_id',
                    'started_at',
                    'completed_at',
                    'created_at',
                    'updated_at',
                ],
            ]);
    }

    public function test_show_other_users_analysis_returns_403(): void
    {
        $otherUser = $this->createOtherUser();

        $analysis = Analysis::create([
            'user_id' => $otherUser->id,
            'url' => 'https://other.com/form',
            'type' => 'manual',
            'status' => 'completed',
            'model' => null,
        ]);

        $response = $this->getJson("/api/analyses/{$analysis->id}");

        $response->assertStatus(403);
    }

    // -----------------------------------------------------------------
    // POST /api/analyses/{analysis}/cancel — Cancel analysis
    // -----------------------------------------------------------------

    public function test_cancel_pending_analysis(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('cancelAnalysis')
            ->once()
            ->andReturn(['status' => 'cancelled']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $analysis = $this->createAnalysis(['status' => 'pending']);

        $response = $this->postJson("/api/analyses/{$analysis->id}/cancel");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Analysis cancelled.');

        $analysis->refresh();
        $this->assertEquals('cancelled', $analysis->status);
        $this->assertNotNull($analysis->completed_at);
    }

    public function test_cancel_analyzing_analysis(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('cancelAnalysis')
            ->once()
            ->andReturn(['status' => 'cancelled']);
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $analysis = $this->createAnalysis(['status' => 'analyzing']);

        $response = $this->postJson("/api/analyses/{$analysis->id}/cancel");

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Analysis cancelled.');

        $analysis->refresh();
        $this->assertEquals('cancelled', $analysis->status);
    }

    public function test_cancel_completed_analysis_returns_422(): void
    {
        $analysis = $this->createAnalysis(['status' => 'completed']);

        $response = $this->postJson("/api/analyses/{$analysis->id}/cancel");

        $response->assertStatus(422)
            ->assertJsonPath('message', 'Only pending or analyzing analyses can be cancelled.');

        // Status should remain unchanged
        $analysis->refresh();
        $this->assertEquals('completed', $analysis->status);
    }

    public function test_cancel_failed_analysis_returns_422(): void
    {
        $analysis = $this->createAnalysis(['status' => 'failed']);

        $response = $this->postJson("/api/analyses/{$analysis->id}/cancel");

        $response->assertStatus(422);
    }

    public function test_cancel_other_users_analysis_returns_403(): void
    {
        $otherUser = $this->createOtherUser();

        $analysis = Analysis::create([
            'user_id' => $otherUser->id,
            'url' => 'https://other.com/form',
            'type' => 'manual',
            'status' => 'pending',
            'model' => null,
        ]);

        $response = $this->postJson("/api/analyses/{$analysis->id}/cancel");

        $response->assertStatus(403);
    }

    public function test_cancel_still_works_when_scraper_call_fails(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('cancelAnalysis')
            ->once()
            ->andThrow(new \RuntimeException('Scraper is down'));
        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $analysis = $this->createAnalysis(['status' => 'analyzing']);

        $response = $this->postJson("/api/analyses/{$analysis->id}/cancel");

        // Cancel should still succeed even when scraper fails
        $response->assertStatus(200)
            ->assertJsonPath('message', 'Analysis cancelled.');

        $analysis->refresh();
        $this->assertEquals('cancelled', $analysis->status);
    }

    // -----------------------------------------------------------------
    // POST /api/analyses/{analysis}/link-task — Link task
    // -----------------------------------------------------------------

    public function test_link_task_to_analysis(): void
    {
        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'draft',
        ]);

        $analysis = $this->createAnalysis();

        $response = $this->postJson("/api/analyses/{$analysis->id}/link-task", [
            'task_id' => $task->id,
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Analysis linked to task.');

        $analysis->refresh();
        $this->assertEquals($task->id, $analysis->task_id);
    }

    public function test_link_task_requires_valid_task_id(): void
    {
        $analysis = $this->createAnalysis();

        $response = $this->postJson("/api/analyses/{$analysis->id}/link-task", [
            'task_id' => '00000000-0000-0000-0000-000000000000',
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['task_id']);
    }

    public function test_link_task_requires_task_id_present(): void
    {
        $analysis = $this->createAnalysis();

        $response = $this->postJson("/api/analyses/{$analysis->id}/link-task", []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['task_id']);
    }

    public function test_link_task_other_users_analysis_returns_403(): void
    {
        $otherUser = $this->createOtherUser();

        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'draft',
        ]);

        $analysis = Analysis::create([
            'user_id' => $otherUser->id,
            'url' => 'https://other.com/form',
            'type' => 'manual',
            'status' => 'completed',
            'model' => null,
        ]);

        $response = $this->postJson("/api/analyses/{$analysis->id}/link-task", [
            'task_id' => $task->id,
        ]);

        $response->assertStatus(403);
    }

    // -----------------------------------------------------------------
    // POST /api/internal/analyses/{id}/result — Store result (internal)
    // -----------------------------------------------------------------

    public function test_store_result_with_correct_internal_key(): void
    {
        $analysis = $this->createAnalysis(['status' => 'analyzing']);

        $result = ['forms' => [['selector' => '#contact-form', 'fields' => []]]];

        $response = $this->postJson("/api/internal/analyses/{$analysis->id}/result", [
            'result' => $result,
        ], [
            'X-Internal-Key' => 'formbot-internal',
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Result stored.');

        $analysis->refresh();
        $this->assertEquals('completed', $analysis->status);
        $this->assertEquals($result, $analysis->result);
        $this->assertNull($analysis->error);
        $this->assertNotNull($analysis->completed_at);
    }

    public function test_store_result_with_error(): void
    {
        $analysis = $this->createAnalysis(['status' => 'analyzing']);

        $response = $this->postJson("/api/internal/analyses/{$analysis->id}/result", [
            'error' => 'Scraper timed out',
        ], [
            'X-Internal-Key' => 'formbot-internal',
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Result stored.');

        $analysis->refresh();
        $this->assertEquals('failed', $analysis->status);
        $this->assertEquals('Scraper timed out', $analysis->error);
        $this->assertNotNull($analysis->completed_at);
    }

    public function test_store_result_with_wrong_internal_key_returns_403(): void
    {
        $analysis = $this->createAnalysis(['status' => 'analyzing']);

        $response = $this->postJson("/api/internal/analyses/{$analysis->id}/result", [
            'result' => ['forms' => []],
        ], [
            'X-Internal-Key' => 'wrong-key',
        ]);

        $response->assertStatus(403);

        // Analysis should remain unchanged
        $analysis->refresh();
        $this->assertEquals('analyzing', $analysis->status);
    }

    public function test_store_result_without_internal_key_returns_403(): void
    {
        $analysis = $this->createAnalysis(['status' => 'analyzing']);

        $response = $this->postJson("/api/internal/analyses/{$analysis->id}/result", [
            'result' => ['forms' => []],
        ]);

        $response->assertStatus(403);
    }

    public function test_store_result_skips_update_for_cancelled_analysis(): void
    {
        $analysis = $this->createAnalysis(['status' => 'cancelled']);

        $response = $this->postJson("/api/internal/analyses/{$analysis->id}/result", [
            'result' => ['forms' => [['selector' => '#form']]],
        ], [
            'X-Internal-Key' => 'formbot-internal',
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('message', 'Analysis already cancelled.');

        // Status should remain cancelled
        $analysis->refresh();
        $this->assertEquals('cancelled', $analysis->status);
        $this->assertNull($analysis->result);
    }

    public function test_store_result_for_nonexistent_analysis_returns_404(): void
    {
        $response = $this->postJson('/api/internal/analyses/00000000-0000-0000-0000-000000000000/result', [
            'result' => ['forms' => []],
        ], [
            'X-Internal-Key' => 'formbot-internal',
        ]);

        $response->assertStatus(404)
            ->assertJsonPath('message', 'Analysis not found.');
    }

    // -----------------------------------------------------------------
    // artisan formbot:cleanup-stale-analyses — Cleanup stale analyses
    // -----------------------------------------------------------------

    public function test_cleanup_marks_stale_pending_analyses_as_timed_out(): void
    {
        // Create a stale pending analysis (created 2 hours ago)
        $stale = $this->createAnalysis(['status' => 'pending']);
        Analysis::where('id', $stale->id)->update([
            'created_at' => now()->subHours(2),
        ]);

        // Create a recent pending analysis (should not be affected)
        $recent = $this->createAnalysis(['status' => 'pending']);

        // Create a stale completed analysis (should not be affected)
        $completed = $this->createAnalysis(['status' => 'completed']);
        Analysis::where('id', $completed->id)->update([
            'created_at' => now()->subHours(2),
        ]);

        Artisan::call('formbot:cleanup-stale-analyses');

        $stale->refresh();
        $this->assertEquals('timed_out', $stale->status);
        $this->assertNotNull($stale->completed_at);

        $recent->refresh();
        $this->assertEquals('pending', $recent->status);

        $completed->refresh();
        $this->assertEquals('completed', $completed->status);
    }

    public function test_cleanup_marks_stale_analyzing_analyses_as_timed_out(): void
    {
        $stale = $this->createAnalysis(['status' => 'analyzing']);
        Analysis::where('id', $stale->id)->update([
            'created_at' => now()->subHours(2),
        ]);

        Artisan::call('formbot:cleanup-stale-analyses');

        $stale->refresh();
        $this->assertEquals('timed_out', $stale->status);
        $this->assertNotNull($stale->completed_at);
    }

    public function test_cleanup_does_nothing_when_no_stale_analyses(): void
    {
        $this->createAnalysis(['status' => 'pending']);
        $this->createAnalysis(['status' => 'completed']);

        $exitCode = Artisan::call('formbot:cleanup-stale-analyses');

        $this->assertEquals(0, $exitCode);
        $this->assertStringContainsString('No stale analyses found', Artisan::output());
    }

    // -----------------------------------------------------------------
    // POST /api/analyze — Analysis creation (always manual)
    // -----------------------------------------------------------------

    public function test_analyze_creates_manual_analysis(): void
    {
        $response = $this->postJson('/api/analyze', [
            'url' => 'https://example.com/form',
        ]);

        $response->assertStatus(200)
            ->assertJsonStructure(['analysis_id', 'message']);

        $analysisId = $response->json('analysis_id');

        $this->assertDatabaseHas('analyses', [
            'id' => $analysisId,
            'user_id' => $this->user->id,
            'url' => 'https://example.com/form',
            'type' => 'manual',
            'status' => 'editing',
        ]);

        // Verify the result contains empty forms
        $analysis = Analysis::find($analysisId);
        $this->assertNotNull($analysis->result);
        $this->assertCount(1, $analysis->result['forms']);
        $this->assertEmpty($analysis->result['forms'][0]['fields']);
    }

    public function test_analyze_validates_url_required(): void
    {
        $response = $this->postJson('/api/analyze', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['url']);
    }

    public function test_analyze_validates_url_format(): void
    {
        $response = $this->postJson('/api/analyze', [
            'url' => 'not-a-valid-url',
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['url']);
    }
}
