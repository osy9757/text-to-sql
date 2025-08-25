import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'dart:html' as html;
import 'package:excel/excel.dart' as excel_lib;
import 'dart:typed_data';

void main() {
  runApp(const TextToSQLApp());
}

class TextToSQLApp extends StatelessWidget {
  const TextToSQLApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Text-to-SQL',
      theme: ThemeData(
        primarySwatch: Colors.green,
        fontFamily: 'Nunito',
        scaffoldBackgroundColor: const Color(0xFFF7F9FA),
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with TickerProviderStateMixin {
  final TextEditingController _textController = TextEditingController();
  String _result = '';
  String _sqlQuery = '';
  List<Map<String, dynamic>> _executionData = [];
  bool _isLoading = false;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  
  // 실시간 처리 과정 표시를 위한 변수들
  List<String> _processingSteps = [];
  String _currentStep = '';
  Map<String, dynamic>? _debugInfo;
  List<Map<String, dynamic>> _chatMessages = [];
  final ScrollController _scrollController = ScrollController();
  
  // 실시간 폴링을 위한 변수들
  Timer? _pollingTimer;
  String? _currentSessionId;
  int _lastMessageCount = 0;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    _textController.dispose();
    _scrollController.dispose();
    _pollingTimer?.cancel();
    super.dispose();
  }

  Future<void> _submitQuery() async {
    if (_textController.text.trim().isEmpty) return;

    setState(() {
      _isLoading = true;
      _result = '';
      _sqlQuery = '';
      _executionData = [];
      _processingSteps = [];
      _currentStep = '';
      _debugInfo = null;
      _chatMessages = [];
    });

    // 폴링 제거 - 단순한 진행 표시만 사용

    try {
      // Python Text-to-SQL 백엔드 API 호출
      const String apiUrl = 'http://127.0.0.1:8000/query';
      
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'query': _textController.text.trim(),
        }),
      );

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        
        print('[DEBUG] Response: ${response.body}'); // 디버그 로그
        
        // API 응답의 success 필드 확인
        bool isSuccess = responseData['success'] ?? false;
        
        setState(() {
          _result = responseData['result'] ?? '⚠️ 응답에서 결과를 찾을 수 없습니다.';
          _sqlQuery = responseData['sql'] ?? '';
          _executionData = List<Map<String, dynamic>>.from(
            responseData['data'] ?? []
          );
          _debugInfo = responseData['debug_info'];
          _currentStep = isSuccess ? '✅ 완료' : '❌ 실패';
        });
        
        // 간단한 완료 처리
        print('[DEBUG] Query completed successfully');
        
        // 세션 데이터 로드 완료 후 loading 종료
        setState(() {
          _isLoading = false;
        });
        
        // 성공한 경우에만 애니메이션 실행
        if (isSuccess) {
          _animationController.forward();
        } else {
          // 실패 시 사용자 친화적인 오류 알림 표시
          String errorType = responseData['error_type'] ?? 'unknown';
          String errorDetails = responseData['error_details'] ?? '';
          
          // 에러 타입별 도움말 메시지
          String helpMessage = _getErrorHelpMessage(errorType);
          
          String enhancedError = _result;
          if (helpMessage.isNotEmpty) {
            enhancedError += '\n\n💡 도움말:\n$helpMessage';
          }
          
          // 디버그 모드에서만 상세 오류 표시
          if (errorDetails.isNotEmpty) {
            enhancedError += '\n\n🔧 기술적 세부사항:\n$errorDetails';
          }
          
          setState(() {
            _result = enhancedError;
          });
          
          // 실패 시 사용자에게 시각적 피드백
          _showErrorSnackBar(errorType);
        }
      } else {
        throw Exception('서버 응답 오류: ${response.statusCode}\n응답: ${response.body}');
      }
    } catch (e) {
      setState(() {
        _result = '오류가 발생했습니다: $e\n\n백엔드 서버가 실행 중인지 확인해주세요 (http://127.0.0.1:8000)';
        _isLoading = false;
      });
    }
  }

  String _getErrorHelpMessage(String errorType) {
    switch (errorType) {
      case 'database_connection':
        return '• 데이터베이스 서버가 실행 중인지 확인해주세요\n• 네트워크 연결 상태를 확인해주세요\n• 잠시 후 다시 시도해보세요';
      case 'sql_generation':
        return '• 질문을 더 구체적으로 작성해보세요\n• 테이블명이나 컬럼명을 정확히 입력했는지 확인해주세요\n• 예: "사용자 테이블에서 최근 가입한 5명을 보여주세요"';
      case 'timeout':
        return '• 더 간단한 질문으로 나눠서 시도해보세요\n• 조건을 더 구체적으로 제한해보세요\n• 잠시 후 다시 시도해보세요';
      case 'validation':
        return '• 질문이 비어있지 않은지 확인해주세요\n• 올바른 한국어로 질문해주세요\n• 예시를 참고해서 질문해보세요';
      case 'processing':
        return '• 잠시 후 다시 시도해주세요\n• 질문을 다르게 표현해보세요\n• 문제가 계속되면 관리자에게 문의하세요';
      default:
        return '• 잠시 후 다시 시도해주세요\n• 문제가 지속되면 관리자에게 문의하세요';
    }
  }

  void _showErrorSnackBar(String errorType) {
    String message = '';
    Color backgroundColor = Colors.red;
    
    switch (errorType) {
      case 'database_connection':
        message = '🔌 데이터베이스 연결 실패';
        backgroundColor = Colors.orange;
        break;
      case 'sql_generation':
        message = '🔍 SQL 생성 오류 - 질문을 다시 확인해주세요';
        backgroundColor = Colors.amber;
        break;
      case 'timeout':
        message = '⏱️ 처리 시간 초과 - 더 간단한 질문으로 시도해주세요';
        backgroundColor = Colors.deepOrange;
        break;
      case 'validation':
        message = '📝 입력 검증 오류 - 질문을 확인해주세요';
        backgroundColor = Colors.purple;
        break;
      default:
        message = '❌ 처리 중 오류가 발생했습니다';
        backgroundColor = Colors.red;
    }
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message, style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: backgroundColor,
        duration: Duration(seconds: 4),
        action: SnackBarAction(
          label: '닫기',
          textColor: Colors.white,
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
          },
        ),
      ),
    );
  }

  Future<void> _checkDatabaseConnection() async {
    try {
      print('[DEBUG] Checking database connection...');
      
      final response = await http.get(Uri.parse('http://127.0.0.1:8000/db-check'));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        bool isSuccess = data['success'] ?? false;
        String message = data['message'] ?? 'DB 연결 상태를 확인할 수 없습니다.';
        
        Color snackBarColor = isSuccess ? Colors.green : Colors.red;
        IconData icon = isSuccess ? Icons.check_circle : Icons.error;
        
        // SnackBar로 결과 표시
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                Icon(icon, color: Colors.white, size: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        message,
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      if (isSuccess && data['connection_time'] != null)
                        Text(
                          '연결 시간: ${data['connection_time']}초',
                          style: const TextStyle(fontSize: 12, color: Colors.white70),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            backgroundColor: snackBarColor,
            duration: const Duration(seconds: 5),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
            action: SnackBarAction(
              label: '닫기',
              textColor: Colors.white,
              onPressed: () {
                ScaffoldMessenger.of(context).hideCurrentSnackBar();
              },
            ),
          ),
        );
        
        // 콘솔에도 자세한 정보 출력
        if (isSuccess) {
          print('[DEBUG] ✅ DB 연결 성공');
          print('[DEBUG] Connection time: ${data['connection_time']}s');
          if (data['database_info'] != null) {
            final dbInfo = data['database_info'];
            print('[DEBUG] Database: ${dbInfo['database']} on ${dbInfo['host']}:${dbInfo['port']}');
          }
        } else {
          print('[DEBUG] ❌ DB 연결 실패: ${data['error_details']}');
        }
        
      } else {
        throw Exception('서버 응답 오류: ${response.statusCode}');
      }
    } catch (e) {
      print('[DEBUG] DB 연결 확인 중 오류: $e');
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.warning, color: Colors.white, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  '🔌 DB 연결 확인 실패: 서버와 통신할 수 없습니다.',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          backgroundColor: Colors.orange,
          duration: const Duration(seconds: 4),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      );
    }
  }

  void _startRealTimePolling(String sessionId) {
    _currentSessionId = sessionId;
    _lastMessageCount = 0;
    
    // 즉시 한 번 로드
    _pollSessionData();
    
    // 1초마다 폴링 시작 (더 빠른 반응)
    _pollingTimer = Timer.periodic(Duration(seconds: 1), (timer) {
      _pollSessionData();
    });
  }
  
  Future<void> _pollSessionData() async {
    if (_currentSessionId == null) return;
    
    try {
      print('[DEBUG] Polling session data: $_currentSessionId');
      final sessionUrl = 'http://127.0.0.1:8000/session/$_currentSessionId';
      final sessionResponse = await http.get(Uri.parse(sessionUrl));
      
      if (sessionResponse.statusCode == 200) {
        final sessionData = jsonDecode(sessionResponse.body);
        List<dynamic> agentInteractions = sessionData['agent_interactions'] ?? [];
        
        // 새로운 메시지가 있는지 확인
        if (agentInteractions.length > _lastMessageCount) {
          print('[DEBUG] New messages found: ${agentInteractions.length - _lastMessageCount}');
          
          // 새로운 메시지들만 추가
          for (int i = _lastMessageCount; i < agentInteractions.length; i++) {
            var interaction = agentInteractions[i];
            String agent = interaction['agent'] ?? 'Unknown Agent';
            String input = interaction['input'] ?? '';
            String output = interaction['output'] ?? '';
            
            // Input 메시지 추가
            if (input.isNotEmpty && input.trim() != '') {
              setState(() {
                _chatMessages.add({
                  'type': 'user',
                  'agent': 'Input to ${_formatAgentName(agent)}',
                  'message': input.length > 500 ? '${input.substring(0, 500)}...' : input,
                  'timestamp': DateTime.now()
                });
              });
              
              await Future.delayed(Duration(milliseconds: 300));
              _scrollToBottom();
            }
            
            // Output 메시지 추가
            if (output.isNotEmpty && output.trim() != '') {
              setState(() {
                _chatMessages.add({
                  'type': 'agent',
                  'agent': _formatAgentName(agent),
                  'message': output.length > 1000 ? '${output.substring(0, 1000)}...' : output,
                  'timestamp': DateTime.now()
                });
              });
              
              await Future.delayed(Duration(milliseconds: 600));
              _scrollToBottom();
            }
          }
          
          _lastMessageCount = agentInteractions.length;
        }
        
        // 처리가 완료되었는지 확인
        if (sessionData['final_result'] != null) {
          print('[DEBUG] Processing completed, stopping polling');
          _pollingTimer?.cancel();
          
          // 최종 결과 메시지 추가
          if (sessionData['final_result']['error_message'] != null) {
            setState(() {
              _chatMessages.add({
                'type': 'error',
                'agent': 'System',
                'message': '❌ ${sessionData['final_result']['error_message']}',
                'timestamp': DateTime.now()
              });
            });
          } else {
            setState(() {
              _chatMessages.add({
                'type': 'success',
                'agent': 'System',
                'message': '✅ 처리 완료!',
                'timestamp': DateTime.now()
              });
            });
          }
          _scrollToBottom();
        }
        
      } else {
        print('[DEBUG] Polling failed with status: ${sessionResponse.statusCode}');
      }
    } catch (e) {
      print('[DEBUG] Polling error: $e');
    }
  }

  void _startLatestSessionPolling() {
    print('[DEBUG] Starting latest session polling');
    _lastMessageCount = 0;
    
    // 1초마다 최신 세션 확인
    _pollingTimer = Timer.periodic(Duration(seconds: 1), (timer) async {
      try {
        final latestSessionUrl = 'http://127.0.0.1:8000/latest-session';
        final latestSessionResponse = await http.get(Uri.parse(latestSessionUrl));
        
        if (latestSessionResponse.statusCode == 200) {
          final latestSessionData = jsonDecode(latestSessionResponse.body);
          String? latestSessionId = latestSessionData['session_id'];
          
          if (latestSessionId != null && latestSessionId != _currentSessionId) {
            print('[DEBUG] Found new session: $latestSessionId');
            _currentSessionId = latestSessionId;
            _lastMessageCount = 0; // 새 세션이므로 카운트 리셋
          }
          
          if (_currentSessionId != null) {
            await _pollSessionData();
          }
        }
      } catch (e) {
        print('[DEBUG] Latest session polling error: $e');
      }
    });
  }

  Future<void> _loadLatestSessionData() async {
    try {
      print('[DEBUG] Trying to load latest session data');
      // 최근 세션 목록을 가져오기 위한 API 호출
      final latestSessionUrl = 'http://127.0.0.1:8000/latest-session';
      final latestSessionResponse = await http.get(Uri.parse(latestSessionUrl));
      
      if (latestSessionResponse.statusCode == 200) {
        final latestSessionData = jsonDecode(latestSessionResponse.body);
        String? latestSessionId = latestSessionData['session_id'];
        
        if (latestSessionId != null) {
          print('[DEBUG] Found latest session: $latestSessionId');
          await _loadSessionData(latestSessionId);
          return;
        }
      }
      
      print('[DEBUG] Could not find any recent sessions');
      setState(() {
        _chatMessages.add({
          'type': 'error',
          'agent': 'System',
          'message': '처리 과정 데이터를 찾을 수 없습니다.',
          'timestamp': DateTime.now()
        });
      });
    } catch (e) {
      print('[DEBUG] Latest session load failed: $e');
      setState(() {
        _chatMessages.add({
          'type': 'error',
          'agent': 'System',
          'message': '처리 과정을 로드하는 중 오류가 발생했습니다.',
          'timestamp': DateTime.now()
        });
      });
    }
  }

  Future<void> _loadSessionData(String sessionId) async {
    try {
      print('[DEBUG] Starting to load session data for: $sessionId');
      // 세션 JSON 파일을 HTTP로 읽어오기 (실제 구현에서는 백엔드 API로 가져와야 함)
      final sessionUrl = 'http://127.0.0.1:8000/session/$sessionId';
      print('[DEBUG] Session URL: $sessionUrl');
      final sessionResponse = await http.get(Uri.parse(sessionUrl));
      
      print('[DEBUG] Session response status: ${sessionResponse.statusCode}');
      
      if (sessionResponse.statusCode == 200) {
        final sessionData = jsonDecode(sessionResponse.body);
        print('[DEBUG] Session data loaded successfully');
        
        List<dynamic> agentInteractions = sessionData['agent_interactions'] ?? [];
        print('[DEBUG] Agent interactions count: ${agentInteractions.length}');
        
        setState(() {
          _chatMessages = [];
        });
        
        // Agent interactions를 채팅 메시지로 변환하며 실시간으로 표시
        for (int i = 0; i < agentInteractions.length; i++) {
          var interaction = agentInteractions[i];
          String agent = interaction['agent'] ?? 'Unknown Agent';
          String input = interaction['input'] ?? '';
          String output = interaction['output'] ?? '';
          
          print('[DEBUG] Processing interaction $i: agent=$agent, input_length=${input.length}, output_length=${output.length}');
          
          // Input 메시지 추가 (에이전트가 받은 입력 내용)
          if (input.isNotEmpty && input.trim() != '') {
            setState(() {
              _chatMessages.add({
                'type': 'user',
                'agent': 'Input to ${_formatAgentName(agent)}',
                'message': input.length > 500 ? '${input.substring(0, 500)}...' : input,
                'timestamp': DateTime.now()
              });
            });
            print('[DEBUG] Added input for $agent, total messages: ${_chatMessages.length}');
            
            await Future.delayed(Duration(milliseconds: 300));
            _scrollToBottom();
          }
          
          // Output 메시지 추가 (에이전트의 실제 응답)
          if (output.isNotEmpty && output.trim() != '') {
            setState(() {
              _chatMessages.add({
                'type': 'agent',
                'agent': _formatAgentName(agent),
                'message': output.length > 1000 ? '${output.substring(0, 1000)}...' : output,
                'timestamp': DateTime.now()
              });
            });
            print('[DEBUG] Added output from $agent, total messages: ${_chatMessages.length}');
            
            await Future.delayed(Duration(milliseconds: 600));
            _scrollToBottom();
          }
        }
        
        print('[DEBUG] Final chat messages count: ${_chatMessages.length}');
        
        // 오류 정보가 있다면 마지막에 추가
        if (sessionData['final_result'] != null && sessionData['final_result']['error_message'] != null) {
          setState(() {
            _chatMessages.add({
              'type': 'error',
              'agent': 'System',
              'message': '❌ ${sessionData['final_result']['error_message']}',
              'timestamp': DateTime.now()
            });
          });
          _scrollToBottom();
        }
        
      } else {
        print('[DEBUG] Session response failed with status: ${sessionResponse.statusCode}');
        print('[DEBUG] Session response body: ${sessionResponse.body}');
      }
    } catch (e) {
      print('[DEBUG] 세션 데이터 로드 실패: $e');
      // 세션 데이터 로드에 실패해도 시뮬레이션 사용하지 않음
      setState(() {
        _chatMessages.add({
          'type': 'error',
          'agent': 'System',
          'message': '실시간 처리 과정을 로드할 수 없습니다. 세션 데이터를 확인해주세요.',
          'timestamp': DateTime.now()
        });
      });
    }
  }
  
  String _formatAgentName(String agent) {
    switch (agent.toLowerCase()) {
      case 'schema_analyst':
        return 'Schema Analyst';
      case 'query_planner':
        return 'Query Planner';
      case 'sql_developer':
        return 'SQL Developer';
      case 'sql_executor':
        return 'SQL Executor';
      case 'quality_validator':
        return 'Quality Validator';
      default:
        return agent;
    }
  }
  
  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(Duration(milliseconds: 100), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }



  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // 메인 컨텐츠
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xFFF7F9FA),
                  Color(0xFFE8F4F8),
                ],
              ),
            ),
            child: SafeArea(
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    children: [
                      // 헤더
                      _buildHeader(),
                      const SizedBox(height: 32),
                      
                      // 입력 영역 (컴팩트하게)
                      _buildCompactInputCard(),
                      const SizedBox(height: 16),
                      
                      // 안내사항 및 주의사항
                      _buildGuidelineCard(),
                      const SizedBox(height: 24),
                      
                      // 결과가 있을 때만 표시
                      if (_result.isNotEmpty || _executionData.isNotEmpty) ...[
                        // 쿼리 결과 (가장 크게)
                        _buildMainResultCard(),
                        const SizedBox(height: 24),
                        
                        // SQL 쿼리 (접을 수 있게)
                        _buildCollapsibleSQLCard(),
                        const SizedBox(height: 16),
                        
                        // 처리 과정 (최소화)
                        _buildMinimizedProcessingCard(),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
          
          // 전체 화면 로딩 오버레이
          if (_isLoading)
            _buildFullScreenLoading(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        // 로고/아이콘
        Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            color: Colors.green[400],
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: Colors.green.withOpacity(0.3),
                blurRadius: 20,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: const Icon(
            Icons.translate,
            color: Colors.white,
            size: 40,
          ),
        ),
        const SizedBox(height: 20),
        
        // 타이틀
        const Text(
          'Text-to-SQL',
          style: TextStyle(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: Color(0xFF2B2D42),
          ),
        ),
        const SizedBox(height: 8),
        
        // 서브타이틀
        Text(
          '자연어로 데이터베이스를 쿼리하세요 🚀',
          style: TextStyle(
            fontSize: 16,
            color: Colors.grey[600],
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildInputCard() {
    return Card(
      elevation: 12,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
      ),
      child: Container(
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 20,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 입력 라벨
            Row(
              children: [
                Icon(
                  Icons.chat_bubble_outline,
                  color: Colors.green[400],
                  size: 24,
                ),
                const SizedBox(width: 12),
                const Text(
                  '질문을 입력하세요',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2B2D42),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // 예시 질문 버튼들
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildSampleButton('사용자의 연령대별 비율을 알려줘'),
                _buildSampleButton('전체 거래액 중 각 연령대가 차지하는 비율을 알려줘'),
                _buildSampleButton('사용자 수를 조회해주세요'),
              ],
            ),
            const SizedBox(height: 20),
            
            // 텍스트 입력 필드
            Container(
              decoration: BoxDecoration(
                color: const Color(0xFFF8F9FA),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: Colors.grey.withOpacity(0.2),
                  width: 2,
                ),
              ),
              child: TextField(
                controller: _textController,
                maxLines: 4,
                minLines: 4,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  hintText: '예시: 전체 유저 중 신분증 인증을 한 유저 비율과 실제로 거래를 진행한 유저 비율을 알려줘',
                  hintStyle: TextStyle(
                    color: Colors.grey[400],
                    fontSize: 14,
                    height: 1.4,
                  ),
                  border: InputBorder.none,
                  focusedBorder: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  errorBorder: InputBorder.none,
                  disabledBorder: InputBorder.none,
                  contentPadding: const EdgeInsets.all(20),
                  alignLabelWithHint: true,
                ),
                style: const TextStyle(
                  fontSize: 16,
                  height: 1.4,
                ),
              ),
            ),
            const SizedBox(height: 24),
            
            // 제출 버튼
            ElevatedButton(
              onPressed: _isLoading ? null : _submitQuery,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green[400],
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 18),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                elevation: 0,
              ),
              child: _isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.send),
                        SizedBox(width: 8),
                        Text(
                          '쿼리 실행',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
            ),
            const SizedBox(height: 12),
            
            // DB 연결 확인 버튼
            OutlinedButton(
              onPressed: _isLoading ? null : _checkDatabaseConnection,
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.blue[600],
                side: BorderSide(color: Colors.blue[300]!),
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.storage_rounded, size: 18),
                  const SizedBox(width: 8),
                  const Text(
                    'DB 연결 확인',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSampleButton(String text) {
    return InkWell(
      onTap: () {
        _textController.text = text;
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.green[50],
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.green.withOpacity(0.3)),
        ),
        child: Text(
          text,
          style: TextStyle(
            fontSize: 12,
            color: Colors.green[700],
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildResultCard() {
    return FadeTransition(
      opacity: _fadeAnimation,
      child: Card(
        elevation: 12,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        child: Container(
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 20,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 결과 헤더
              Row(
                children: [
                  Icon(
                    _isLoading 
                        ? Icons.hourglass_empty 
                        : _result.startsWith('❌') 
                            ? Icons.error_outline 
                            : Icons.check_circle,
                    color: _isLoading 
                        ? Colors.orange 
                        : _result.startsWith('❌') 
                            ? Colors.red[400] 
                            : Colors.green[400],
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _isLoading 
                        ? '처리 중...' 
                        : _result.startsWith('❌') 
                            ? '오류 발생' 
                            : '결과',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: _result.startsWith('❌') 
                          ? Colors.red[800] 
                          : const Color(0xFF2B2D42),
                    ),
                  ),
                ],
              ),
              
              if (!_isLoading) ...[
                const SizedBox(height: 20),
                
                // 결과 텍스트
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: _result.startsWith('❌') ? Colors.red[50] : Colors.green[50],
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: _result.startsWith('❌') 
                          ? Colors.red.withOpacity(0.2) 
                          : Colors.green.withOpacity(0.2),
                      width: 1,
                    ),
                  ),
                  child: SingleChildScrollView(
                    child: Text(
                      _result,
                      style: TextStyle(
                        fontSize: 16,
                        height: 1.5,
                        color: _result.startsWith('❌') 
                            ? Colors.red[800] 
                            : const Color(0xFF2B2D42),
                      ),
                    ),
                  ),
                ),
                
                // 실행 데이터 테이블
                if (_executionData.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  _buildDataTable(),
                ],
                
                if (_sqlQuery.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  
                  // SQL 쿼리 표시
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          Icon(
                            Icons.code,
                            color: Colors.blue[400],
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          const Text(
                            '생성된 SQL 쿼리',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF2B2D42),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: const Color(0xFF2B2D42),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: SingleChildScrollView(
                          scrollDirection: Axis.vertical,
                          child: SelectableText(
                            _formatSQL(_sqlQuery),
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 13,
                              color: Colors.white,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ] else
                const Padding(
                  padding: EdgeInsets.all(32.0),
                  child: Center(
                    child: Column(
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 16),
                        Text('쿼리를 실행 중입니다...'),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDataTable() {
    if (_executionData.isEmpty) return const SizedBox.shrink();

    final columns = _executionData.first.keys.toList();
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.table_chart,
              color: Colors.blue[400],
              size: 20,
            ),
            const SizedBox(width: 8),
            const Text(
              '실행 결과',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF2B2D42),
              ),
            ),
            const Spacer(),
            // 복사 버튼
            IconButton(
              onPressed: _copyTableToClipboard,
              icon: const Icon(Icons.copy, size: 18),
              tooltip: '테이블 복사',
              style: IconButton.styleFrom(
                foregroundColor: Colors.blue[600],
                padding: const EdgeInsets.all(8),
              ),
            ),
            // 엑셀 다운로드 버튼
            IconButton(
              onPressed: _downloadExcel,
              icon: const Icon(Icons.download, size: 18),
              tooltip: '엑셀 다운로드',
              style: IconButton.styleFrom(
                foregroundColor: Colors.green[600],
                padding: const EdgeInsets.all(8),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey.withOpacity(0.3)),
            borderRadius: BorderRadius.circular(8),
          ),
          child: SelectionArea(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                headingRowColor: MaterialStateProperty.all(Colors.grey[100]),
                columns: columns.map((column) => DataColumn(
                  label: Text(
                    column,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                )).toList(),
                rows: _executionData.map((row) => DataRow(
                  cells: columns.map((column) => DataCell(
                    Text(row[column].toString()),
                  )).toList(),
                )).toList(),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProcessingPanel() {
    double panelHeight = MediaQuery.of(context).size.height * 0.7; // 화면 높이의 70%
    
    return Card(
      elevation: 8,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
      ),
      child: Container(
        height: panelHeight, // 반응형 높이
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          children: [
            // 패널 헤더
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.blue[50],
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(20),
                  topRight: Radius.circular(20),
                ),
                border: Border(
                  bottom: BorderSide(
                    color: Colors.blue.withOpacity(0.1),
                    width: 1,
                  ),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.smart_toy_outlined,
                    color: Colors.blue[600],
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    '진행 상황',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF2B2D42),
                    ),
                  ),
                  const Spacer(),
                  if (_isLoading)
                    SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.blue[600],
                      ),
                    ),
                ],
              ),
            ),
            
            // 진행 상황 표시 영역
            Expanded(
              child: _isLoading
                  ? _buildSimpleProgressIndicator()
                  : (_chatMessages.isEmpty 
                      ? _buildEmptyState()
                      : _buildCompletionMessage()),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.help_outline,
            size: 64,
            color: Colors.blue[300],
          ),
          const SizedBox(height: 24),
          Text(
            '💡 이렇게 물어보세요',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.blue[700],
            ),
          ),
          const SizedBox(height: 20),
          _buildHelpItem('👥', '사용자 수를 조회해주세요'),
          _buildHelpItem('📊', '연령대별 비율을 알려주세요'),
          _buildHelpItem('💰', '월별 거래액을 보여주세요'),
          _buildHelpItem('📈', '최근 거래 현황을 분석해주세요'),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.amber[50],
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.amber[200]!),
            ),
            child: Row(
              children: [
                Icon(Icons.schedule, color: Colors.amber[700]),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '복잡한 질문일수록 분석 시간이 더 걸려요',
                    style: TextStyle(
                      color: Colors.amber[800],
                      fontSize: 14,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildHelpItem(String emoji, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.grey[50],
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.grey[200]!),
        ),
        child: Row(
          children: [
            Text(emoji, style: TextStyle(fontSize: 18)),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: TextStyle(
                  color: Colors.grey[700],
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildChatMessages() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: _chatMessages.length + (_debugInfo != null ? 1 : 0),
      itemBuilder: (context, index) {
        if (index < _chatMessages.length) {
          return _buildChatMessage(_chatMessages[index]);
        } else {
          return _buildFinalResultCard();
        }
      },
    );
  }
  
  Widget _buildChatMessage(Map<String, dynamic> message) {
    bool isUser = message['type'] == 'user';
    bool isError = message['type'] == 'error';
    bool isSuccess = message['type'] == 'success';
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (isUser) ...[
            // 사용자 메시지 - 왼쪽 정렬 (카카오톡 스타일)
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: Colors.green[400],
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                Icons.person,
                color: Colors.white,
                size: 16,
              ),
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'User',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Colors.green[700],
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.4,
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: Colors.green[100],
                      borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(4),
                        topRight: Radius.circular(16),
                        bottomLeft: Radius.circular(16),
                        bottomRight: Radius.circular(16),
                      ),
                      border: Border.all(
                        color: Colors.green.withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: Text(
                      message['message'],
                      style: TextStyle(
                        fontSize: 14,
                        color: const Color(0xFF2B2D42),
                        height: 1.4,
                      ),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _formatTime(message['timestamp']),
                    style: TextStyle(
                      fontSize: 9,
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
            ),
            // 오른쪽 여백
            SizedBox(width: 40),
          ] else ...[
            // Agent 메시지 - 오른쪽 정렬 (카카오톡 스타일)
            // 왼쪽 여백
            SizedBox(width: 40),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    message['agent'],
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: isError ? Colors.red[700] : isSuccess ? Colors.green[700] : Colors.blue[700],
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.5,
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: isError ? Colors.red[50] : isSuccess ? Colors.green[50] : Colors.blue[50],
                      borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(16),
                        topRight: Radius.circular(4),
                        bottomLeft: Radius.circular(16),
                        bottomRight: Radius.circular(16),
                      ),
                      border: Border.all(
                        color: isError 
                            ? Colors.red.withOpacity(0.3)
                            : isSuccess
                                ? Colors.green.withOpacity(0.3)
                                : Colors.blue.withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: Text(
                      message['message'],
                      style: TextStyle(
                        fontSize: 14,
                        color: const Color(0xFF2B2D42),
                        height: 1.4,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _formatTime(message['timestamp']),
                    style: TextStyle(
                      fontSize: 9,
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: isError ? Colors.red[400] : isSuccess ? Colors.green[400] : Colors.blue[400],
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                isError ? Icons.error : isSuccess ? Icons.check_circle : Icons.smart_toy,
                color: Colors.white,
                size: 16,
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Widget _buildSimpleProgressIndicator() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // 진행률 원형 표시
          SizedBox(
            width: 100,
            height: 100,
            child: Stack(
              children: [
                Center(
                  child: SizedBox(
                    width: 100,
                    height: 100,
                    child: CircularProgressIndicator(
                      strokeWidth: 6,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.blue[400]!),
                    ),
                  ),
                ),
                Center(
                  child: Icon(
                    Icons.analytics_outlined,
                    size: 32,
                    color: Colors.blue[600],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text(
            '📊 분석 중...',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: Colors.blue[700],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '데이터베이스에서 정보를 찾고 있어요',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            '잠시만 기다려 주세요',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[500],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletionMessage() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 64,
            color: Colors.green[500],
          ),
          const SizedBox(height: 20),
          Text(
            '✅ 분석 완료!',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: Colors.green[700],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '결과를 확인해보세요',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 24),
          TextButton.icon(
            onPressed: () {
              setState(() {
                _result = '';
                _isLoading = false;
                _chatMessages.clear();
                _textController.clear();
              });
            },
            icon: Icon(Icons.refresh, color: Colors.blue[600]),
            label: Text(
              '새 질문하기',
              style: TextStyle(color: Colors.blue[600]),
            ),
            style: TextButton.styleFrom(
              backgroundColor: Colors.blue[50],
              padding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildFinalResultCard() {
    if (_debugInfo == null) return const SizedBox.shrink();
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.green[50],
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: Colors.green.withOpacity(0.3),
            width: 2,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.check_circle,
                  color: Colors.green[600],
                  size: 20,
                ),
                const SizedBox(width: 8),
                const Text(
                  '실행 완료',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2B2D42),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ..._debugInfo!.entries.map((entry) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Text(
                      '${entry.key}: ',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF2B2D42),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        '${entry.value}',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[700],
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
  
  String _formatTime(DateTime timestamp) {
    return '${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}:${timestamp.second.toString().padLeft(2, '0')}';
  }
  
  String _formatSQL(String sql) {
    if (sql.isEmpty) return sql;
    
    // SQL 키워드들
    const keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 
                     'GROUP BY', 'ORDER BY', 'HAVING', 'UNION', 'INSERT', 'UPDATE', 'DELETE',
                     'AS', 'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END'];
    
    String formatted = sql;
    
    // 주요 키워드 앞에서 줄바꿈
    formatted = formatted.replaceAllMapped(
      RegExp(r'\s+(SELECT|FROM|WHERE|JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN|GROUP BY|ORDER BY|HAVING|UNION)\s+', caseSensitive: false),
      (match) => '\n${match.group(1)!.toUpperCase()} '
    );
    
    // 콤마 후 줄바꿈 (SELECT 절에서)
    formatted = formatted.replaceAllMapped(
      RegExp(r',\s*(?=[a-zA-Z_])', caseSensitive: false),
      (match) => ',\n    '
    );
    
    // ON 절 정리
    formatted = formatted.replaceAllMapped(
      RegExp(r'\s+ON\s+', caseSensitive: false),
      (match) => '\n  ON '
    );
    
    // AND, OR 절 들여쓰기
    formatted = formatted.replaceAllMapped(
      RegExp(r'\s+(AND|OR)\s+', caseSensitive: false),
      (match) => '\n    ${match.group(1)!.toUpperCase()} '
    );
    
    // 첫 줄 앞의 불필요한 줄바꿈 제거
    formatted = formatted.trim();
    
    return formatted;
  }

  // 엑셀 다운로드 기능
  void _downloadExcel() {
    if (_executionData.isEmpty) return;

    // Excel 워크북 생성
    final excel = excel_lib.Excel.createExcel();
    final sheet = excel['Sheet1'];

    // 컬럼명 추가
    final columns = _executionData.first.keys.toList();
    for (int i = 0; i < columns.length; i++) {
      sheet.cell(excel_lib.CellIndex.indexByColumnRow(columnIndex: i, rowIndex: 0))
          .value = excel_lib.TextCellValue(columns[i]);
    }

    // 데이터 추가
    for (int rowIndex = 0; rowIndex < _executionData.length; rowIndex++) {
      final row = _executionData[rowIndex];
      for (int colIndex = 0; colIndex < columns.length; colIndex++) {
        final value = row[columns[colIndex]];
        sheet.cell(excel_lib.CellIndex.indexByColumnRow(columnIndex: colIndex, rowIndex: rowIndex + 1))
            .value = excel_lib.TextCellValue(value?.toString() ?? '');
      }
    }

    // 바이너리 데이터로 변환
    final fileBytes = excel.encode();
    final blob = html.Blob([Uint8List.fromList(fileBytes!)]);
    final url = html.Url.createObjectUrlFromBlob(blob);
    
    // 다운로드 링크 생성 및 클릭
    final anchor = html.AnchorElement(href: url)
      ..setAttribute('download', 'query_results_${DateTime.now().millisecondsSinceEpoch}.xlsx')
      ..click();
    
    // URL 해제
    html.Url.revokeObjectUrl(url);
  }

  // 테이블 데이터를 클립보드에 복사하는 기능
  void _copyTableToClipboard() {
    if (_executionData.isEmpty) return;

    final columns = _executionData.first.keys.toList();
    String tsvData = '';

    // 헤더 추가
    tsvData += columns.join('\t') + '\n';

    // 데이터 행 추가
    for (final row in _executionData) {
      final values = columns.map((col) => row[col]?.toString() ?? '').toList();
      tsvData += values.join('\t') + '\n';
    }

    // 클립보드에 복사
    Clipboard.setData(ClipboardData(text: tsvData));
    
    // 사용자에게 알림
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('📋 테이블 데이터가 클립보드에 복사되었습니다!'),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }

  // 컴팩트한 입력 카드
  Widget _buildCompactInputCard() {
    return Card(
      elevation: 8,
      shadowColor: Colors.blue.withOpacity(0.2),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '💬 무엇이 궁금하신가요?',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: Color(0xFF2B2D42),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    onSubmitted: (_) => _submitQuery(),
                    decoration: InputDecoration(
                      hintText: '예: 사용자별 거래 내역을 알려주세요',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide(color: Colors.grey.shade300),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(color: Colors.blue),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton(
                  onPressed: _submitQuery,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 24,
                      vertical: 12,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text('전송'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // 안내사항 및 주의사항 카드
  Widget _buildGuidelineCard() {
    return Card(
      color: Colors.orange.shade50,
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.info_outline, 
                     color: Colors.orange.shade700, size: 20),
                const SizedBox(width: 8),
                Text(
                  '사용 안내',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.orange.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '• 한국어로 자연스럽게 질문해주세요\n'
              '• 구체적인 조건이나 기간을 포함하면 더 정확합니다',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                border: Border.all(color: Colors.red.shade200),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.warning_amber_outlined, 
                       color: Colors.red.shade700, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '⚠️ 이 결과는 임시 확인용입니다. 정확한 분석은 담당자에게 문의하세요.',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: Colors.red.shade700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 메인 결과 카드 (가장 크게)
  Widget _buildMainResultCard() {
    if (_executionData.isEmpty && _result.isEmpty) {
      return Container();
    }

    return Card(
      elevation: 8,
      shadowColor: Colors.green.withOpacity(0.2),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.table_chart, color: Colors.green.shade600),
                const SizedBox(width: 12),
                const Text(
                  '📊 쿼리 결과',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2B2D42),
                  ),
                ),
                const Spacer(),
                if (_executionData.isNotEmpty) ...[
                  Text(
                    '총 ${_executionData.length}건',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade600,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(width: 16),
                  // 복사 버튼
                  IconButton(
                    onPressed: _copyTableToClipboard,
                    icon: const Icon(Icons.copy, size: 20),
                    tooltip: '테이블 복사',
                    style: IconButton.styleFrom(
                      foregroundColor: Colors.blue[600],
                      padding: const EdgeInsets.all(8),
                    ),
                  ),
                  // 엑셀 다운로드 버튼
                  IconButton(
                    onPressed: _downloadExcel,
                    icon: const Icon(Icons.download, size: 20),
                    tooltip: '엑셀 다운로드',
                    style: IconButton.styleFrom(
                      foregroundColor: Colors.green[600],
                      padding: const EdgeInsets.all(8),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 16),
            
            // 데이터 테이블
            if (_executionData.isNotEmpty) ...[
              Container(
                constraints: const BoxConstraints(
                  maxHeight: 600, // 최대 높이 설정
                ),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.withOpacity(0.3)),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: SelectionArea(
                  child: SingleChildScrollView(
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: DataTable(
                        headingRowColor: MaterialStateProperty.all(
                          Colors.green.shade50,
                        ),
                        columns: _executionData.first.keys
                            .map((column) => DataColumn(
                                  label: Text(
                                    column,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                    ),
                                  ),
                                ))
                            .toList(),
                        rows: _executionData
                            .map((row) => DataRow(
                                  cells: _executionData.first.keys
                                      .map((column) => DataCell(
                                            Text(
                                              row[column].toString(),
                                              style: const TextStyle(fontSize: 13),
                                            ),
                                          ))
                                      .toList(),
                                ))
                            .toList(),
                      ),
                    ),
                  ),
                ),
              ),
            ] else if (_result.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: Text(
                  _result,
                  style: const TextStyle(
                    fontSize: 14,
                    color: Color(0xFF2B2D42),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // 접을 수 있는 SQL 카드
  Widget _buildCollapsibleSQLCard() {
    if (_sqlQuery.isEmpty) return Container();

    return Card(
      elevation: 4,
      child: ExpansionTile(
        initiallyExpanded: false,
        leading: Icon(Icons.code, color: Colors.purple.shade600),
        title: const Text(
          '🔍 생성된 SQL 쿼리',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: SelectableText(
              _formatSQL(_sqlQuery),
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 12,
                color: Color(0xFF2B2D42),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // 최소화된 처리 과정 카드
  Widget _buildMinimizedProcessingCard() {
    if (_chatMessages.isEmpty) return Container();

    return Card(
      elevation: 2,
      child: ExpansionTile(
        initiallyExpanded: false,
        leading: Icon(Icons.settings, color: Colors.grey.shade600, size: 20),
        title: Text(
          '⚙️ 처리 과정 (${_chatMessages.length}단계)',
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
        ),
        children: [
          Container(
            constraints: const BoxConstraints(maxHeight: 300),
            padding: const EdgeInsets.all(16),
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: _chatMessages.length,
              itemBuilder: (context, index) {
                final message = _chatMessages[index];
                final isAgent = message['type'] == 'agent';
                
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: isAgent ? Colors.blue.shade50 : Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        message['agent'] ?? 'Unknown',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: isAgent ? Colors.blue.shade700 : Colors.grey.shade600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        message['message'] ?? '',
                        style: const TextStyle(fontSize: 11),
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // 전체 화면 로딩 오버레이
  Widget _buildFullScreenLoading() {
    return Container(
      color: Colors.black.withOpacity(0.7),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 60,
              height: 60,
              child: CircularProgressIndicator(
                strokeWidth: 4,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            ),
            SizedBox(height: 24),
            Text(
              '🤖 AI가 쿼리를 분석하고 있습니다...',
              style: TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
            SizedBox(height: 8),
            Text(
              '잠시만 기다려주세요',
              style: TextStyle(
                color: Colors.white70,
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    );
  }
}