<?php

namespace Tests\Feature;

use App\Jobs\AnalyzeLoginAndTargetJob;
use App\Models\Task;
use App\Models\User;
use App\Services\ScraperClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;
use Laravel\Passport\Passport;
use Mockery;
use Tests\TestCase;

class LoginAnalysisTest extends TestCase
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
    // POST /analyze/login-and-target
    // -----------------------------------------------------------------

    public function test_analyze_login_and_target_dispatches_job(): void
    {
        Queue::fake();

        $response = $this->postJson('/api/analyze/login-and-target', [
            'login_url' => 'https://example.com/login',
            'target_url' => 'https://example.com/dashboard',
            'login_form_selector' => '#login-form',
            'login_submit_selector' => '#submit-btn',
            'login_fields' => [
                [
                    'field_selector' => '#username',
                    'value' => 'admin',
                ],
                [
                    'field_selector' => '#password',
                    'value' => 'secret123',
                    'is_sensitive' => true,
                ],
            ],
            'needs_vnc' => false,
        ]);

        $response->assertStatus(200)
            ->assertJsonStructure(['analysis_id', 'message']);

        $this->assertNotEmpty($response->json('analysis_id'));

        Queue::assertPushed(AnalyzeLoginAndTargetJob::class, function ($job) {
            return $job->loginUrl === 'https://example.com/login'
                && $job->targetUrl === 'https://example.com/dashboard'
                && $job->loginFormSelector === '#login-form'
                && $job->loginSubmitSelector === '#submit-btn'
                && $job->needsVnc === false
                && count($job->loginFields) === 2;
        });
    }

    public function test_analyze_login_and_target_encrypts_sensitive_fields(): void
    {
        Queue::fake();

        $response = $this->postJson('/api/analyze/login-and-target', [
            'login_url' => 'https://example.com/login',
            'target_url' => 'https://example.com/dashboard',
            'login_form_selector' => '#login-form',
            'login_submit_selector' => '#submit-btn',
            'login_fields' => [
                [
                    'field_selector' => '#password',
                    'value' => 'my-secret-password',
                    'is_sensitive' => true,
                ],
            ],
        ]);

        $response->assertStatus(200);

        Queue::assertPushed(AnalyzeLoginAndTargetJob::class, function ($job) {
            $passwordField = $job->loginFields[0];

            // The value should be encrypted (different from original)
            $this->assertNotEquals('my-secret-password', $passwordField['value']);

            // The encrypted flag should be set
            $this->assertTrue($passwordField['encrypted']);

            return true;
        });
    }

    public function test_analyze_login_and_target_validation_missing_login_url(): void
    {
        $response = $this->postJson('/api/analyze/login-and-target', [
            'target_url' => 'https://example.com/dashboard',
            'login_form_selector' => '#login-form',
            'login_submit_selector' => '#submit-btn',
            'login_fields' => [],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['login_url']);
    }

    public function test_analyze_login_and_target_validation_missing_target_url(): void
    {
        $response = $this->postJson('/api/analyze/login-and-target', [
            'login_url' => 'https://example.com/login',
            'login_form_selector' => '#login-form',
            'login_submit_selector' => '#submit-btn',
            'login_fields' => [],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['target_url']);
    }

    public function test_analyze_login_and_target_validation_invalid_urls(): void
    {
        $response = $this->postJson('/api/analyze/login-and-target', [
            'login_url' => 'not-a-url',
            'target_url' => 'also-not-a-url',
            'login_form_selector' => '#login-form',
            'login_submit_selector' => '#submit-btn',
            'login_fields' => [],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['login_url', 'target_url']);
    }

    public function test_analyze_login_and_target_validation_missing_selectors(): void
    {
        $response = $this->postJson('/api/analyze/login-and-target', [
            'login_url' => 'https://example.com/login',
            'target_url' => 'https://example.com/dashboard',
            'login_fields' => [],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['login_form_selector', 'login_submit_selector']);
    }

    public function test_analyze_login_and_target_with_vnc(): void
    {
        Queue::fake();

        $response = $this->postJson('/api/analyze/login-and-target', [
            'login_url' => 'https://example.com/login',
            'target_url' => 'https://example.com/dashboard',
            'login_form_selector' => '#login-form',
            'login_submit_selector' => '#submit-btn',
            'login_fields' => [
                ['field_selector' => '#user', 'value' => 'admin'],
            ],
            'needs_vnc' => true,
        ]);

        $response->assertStatus(200);

        Queue::assertPushed(AnalyzeLoginAndTargetJob::class, function ($job) {
            return $job->needsVnc === true;
        });
    }

    // -----------------------------------------------------------------
    // POST /analyze/resume-vnc
    // -----------------------------------------------------------------

    public function test_resume_analysis_vnc(): void
    {
        $mockScraperClient = Mockery::mock(ScraperClient::class);
        $mockScraperClient->shouldReceive('resumeAnalysisVnc')
            ->once()
            ->with('vnc-session-123', 'analysis-456')
            ->andReturn(['status' => 'resumed', 'execution_id' => 'analysis-456']);

        $this->app->instance(ScraperClient::class, $mockScraperClient);

        $response = $this->postJson('/api/analyze/resume-vnc', [
            'session_id' => 'vnc-session-123',
            'analysis_id' => 'analysis-456',
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('status', 'resumed');
    }

    public function test_resume_analysis_vnc_validation(): void
    {
        $response = $this->postJson('/api/analyze/resume-vnc', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['session_id', 'analysis_id']);
    }

    // -----------------------------------------------------------------
    // Task CRUD with login fields
    // -----------------------------------------------------------------

    public function test_create_task_with_requires_login(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Login Task',
            'target_url' => 'https://example.com/dashboard',
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
            'login_every_time' => false,
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.requires_login', true)
            ->assertJsonPath('data.login_url', 'https://example.com/login')
            ->assertJsonPath('data.login_every_time', false);

        $this->assertDatabaseHas('tasks', [
            'name' => 'Login Task',
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
            'login_every_time' => false,
        ]);
    }

    public function test_create_task_without_login_defaults(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Simple Task',
            'target_url' => 'https://example.com/form',
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('data.requires_login', false)
            ->assertJsonPath('data.login_url', null)
            ->assertJsonPath('data.login_every_time', true);
    }

    public function test_update_task_adds_login_config(): void
    {
        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Test Task',
            'target_url' => 'https://example.com/form',
            'status' => 'draft',
        ]);

        $response = $this->putJson("/api/tasks/{$task->id}", [
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
            'login_every_time' => false,
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('data.requires_login', true)
            ->assertJsonPath('data.login_url', 'https://example.com/login')
            ->assertJsonPath('data.login_every_time', false);

        $this->assertDatabaseHas('tasks', [
            'id' => $task->id,
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
        ]);
    }

    public function test_login_url_required_when_requires_login_is_true(): void
    {
        $response = $this->postJson('/api/tasks', [
            'name' => 'Login Task',
            'target_url' => 'https://example.com/dashboard',
            'requires_login' => true,
            // login_url missing
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['login_url']);
    }

    public function test_get_task_includes_login_fields(): void
    {
        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Login Task',
            'target_url' => 'https://example.com/dashboard',
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
            'login_every_time' => false,
            'status' => 'draft',
        ]);

        $response = $this->getJson("/api/tasks/{$task->id}");

        $response->assertStatus(200)
            ->assertJsonPath('data.requires_login', true)
            ->assertJsonPath('data.login_url', 'https://example.com/login')
            ->assertJsonPath('data.login_every_time', false);
    }

    public function test_login_session_data_not_exposed_in_api(): void
    {
        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Login Task',
            'target_url' => 'https://example.com/dashboard',
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
            'login_session_data' => '{"cookies": []}',
            'status' => 'draft',
        ]);

        $response = $this->getJson("/api/tasks/{$task->id}");

        $response->assertStatus(200);

        // login_session_data should NOT be in the response
        $data = $response->json('data');
        $this->assertArrayNotHasKey('login_session_data', $data);
    }

    public function test_clone_task_with_login_preserves_login_config(): void
    {
        $task = Task::create([
            'user_id' => $this->user->id,
            'name' => 'Login Task',
            'target_url' => 'https://example.com/dashboard',
            'requires_login' => true,
            'login_url' => 'https://example.com/login',
            'login_every_time' => false,
            'login_session_data' => '{"cookies": ["session=abc"]}',
            'status' => 'draft',
        ]);

        $response = $this->postJson("/api/tasks/{$task->id}/clone");

        $response->assertStatus(201);

        $cloned = $response->json('data');

        // Login config should be copied
        $this->assertTrue($cloned['requires_login']);
        $this->assertEquals('https://example.com/login', $cloned['login_url']);
        $this->assertFalse($cloned['login_every_time']);

        // login_session_data should NOT be copied (and not in response)
        $this->assertArrayNotHasKey('login_session_data', $cloned);

        // Verify in DB that session data was cleared
        $clonedTask = Task::find($cloned['id']);
        $this->assertNull($clonedTask->login_session_data);
    }
}
