import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

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
    super.dispose();
  }

  Future<void> _submitQuery() async {
    if (_textController.text.trim().isEmpty) return;

    setState(() {
      _isLoading = true;
      _result = '';
      _sqlQuery = '';
      _executionData = [];
    });

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
        
        setState(() {
          _result = responseData['result'] ?? '✅ 쿼리가 성공적으로 실행되었습니다.';
          _sqlQuery = responseData['sql'] ?? '';
          _executionData = List<Map<String, dynamic>>.from(
            responseData['data'] ?? []
          );
          _isLoading = false;
        });
        
        _animationController.forward();
      } else {
        throw Exception('서버 응답 오류: ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _result = '오류가 발생했습니다: $e\n\n백엔드 서버가 실행 중인지 확인해주세요 (http://127.0.0.1:8000)';
        _isLoading = false;
      });
    }
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
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
                  const SizedBox(height: 40),
                  
                  // 메인 컨텐츠
                  Container(
                    constraints: const BoxConstraints(maxWidth: 900),
                    child: Column(
                      children: [
                        // 입력 카드
                        _buildInputCard(),
                        const SizedBox(height: 32),
                        
                        // 결과 표시
                        if (_result.isNotEmpty || _isLoading)
                          _buildResultCard(),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
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
                decoration: InputDecoration(
                  hintText: '예시를 클릭하거나 직접 질문을 입력하세요...\n\n• 20대 사용자의 수를 알려주세요\n• 최근 일주일간 거래액을 조회해주세요\n• 연령대별 사용자 비율을 보여주세요',
                  hintStyle: TextStyle(
                    color: Colors.grey[400],
                    fontSize: 14,
                  ),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.all(20),
                ),
                style: const TextStyle(
                  fontSize: 16,
                  height: 1.5,
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
                    _isLoading ? Icons.hourglass_empty : Icons.check_circle,
                    color: _isLoading ? Colors.orange : Colors.green[400],
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _isLoading ? '처리 중...' : '결과',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF2B2D42),
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
                    color: Colors.green[50],
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: Colors.green.withOpacity(0.2),
                      width: 1,
                    ),
                  ),
                  child: Text(
                    _result,
                    style: const TextStyle(
                      fontSize: 16,
                      height: 1.5,
                      color: Color(0xFF2B2D42),
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
                          scrollDirection: Axis.horizontal,
                          child: Text(
                            _sqlQuery,
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
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey.withOpacity(0.3)),
            borderRadius: BorderRadius.circular(8),
          ),
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
      ],
    );
  }
}