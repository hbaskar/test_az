#!/usr/bin/env python3
"""
Chunking Quality Comparison Tool
==============================

Compares basic chunking vs OpenAI enhanced chunking to evaluate quality improvements.

This tool will:
1. Process documents with both chunking methods
2. Compare chunk count, size distribution, and content quality
3. Analyze key phrase extraction effectiveness
4. Measure processing time and costs
5. Generate detailed comparison reports
"""

import os
import sys
import json
import time
import statistics
from typing import List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from enhanced_test_runner_multi_db import MultiDatabaseAzureFunctionTester, create_database_manager
    from database_config import DatabaseConfig
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure this script is in the same directory as the test runner files")
    sys.exit(1)

@dataclass
class ChunkingResult:
    """Results from a chunking operation"""
    method: str
    chunk_count: int
    chunks: List[Dict[str, Any]]
    processing_time: float
    total_size: int
    avg_chunk_size: float
    min_chunk_size: int
    max_chunk_size: int
    has_key_phrases: bool
    has_summaries: bool
    error: str = None

@dataclass
class ComparisonMetrics:
    """Comparison metrics between two chunking methods"""
    document_name: str
    basic_result: ChunkingResult
    enhanced_result: ChunkingResult
    chunk_count_diff: int
    avg_size_diff: float
    size_distribution_comparison: Dict[str, Any]
    quality_score: float
    recommendations: List[str]

class ChunkingQualityAnalyzer:
    """Analyzes and compares different chunking approaches"""
    
    def __init__(self, verbose: bool = True, db_type: str = 'sqlite'):
        """Initialize the analyzer"""
        self.verbose = verbose
        self.db_type = db_type
        
        # Initialize database connection
        try:
            self.db = create_database_manager(db_type)
            if verbose:
                print(f"✅ Connected to {db_type.upper()} database")
        except Exception as e:
            print(f"⚠️ Could not connect to database: {e}")
            self.db = None
        
        # Initialize test runner for Azure Function calls
        self.function_url = os.getenv('AZURE_FUNCTION_URL', 'http://localhost:7071/api/process-document')
        self.test_runner = MultiDatabaseAzureFunctionTester(
            azure_function_url=self.function_url.split('/api/')[0] if '/api/' in self.function_url else self.function_url,
            verbose=verbose,
            enable_db=False,  # We'll manage DB separately
            db_type=db_type
        )
    
    def extract_basic_chunks(self, document_text: str, filename: str) -> ChunkingResult:
        """Extract chunks using basic paragraph-based method"""
        start_time = time.time()
        
        try:
            # Basic chunking logic (similar to current enhanced_test_runner)
            paragraphs = [p.strip() for p in document_text.split('\n\n') if p.strip()]
            
            if not paragraphs:
                # Fallback: split by sentences
                import re
                sentences = re.split(r'[.!?]+', document_text)
                paragraphs = [s.strip() for s in sentences if s.strip()]
            
            chunks = []
            total_size = 0
            
            for i, paragraph in enumerate(paragraphs):
                chunk_size = len(paragraph)
                total_size += chunk_size
                
                chunk = {
                    'id': i + 1,
                    'title': f"Section {i + 1}",
                    'content': paragraph,
                    'size': chunk_size,
                    'index': i
                }
                chunks.append(chunk)
            
            processing_time = time.time() - start_time
            
            return ChunkingResult(
                method="Basic Paragraph",
                chunk_count=len(chunks),
                chunks=chunks,
                processing_time=processing_time,
                total_size=total_size,
                avg_chunk_size=total_size / len(chunks) if chunks else 0,
                min_chunk_size=min(c['size'] for c in chunks) if chunks else 0,
                max_chunk_size=max(c['size'] for c in chunks) if chunks else 0,
                has_key_phrases=False,
                has_summaries=False
            )
            
        except Exception as e:
            return ChunkingResult(
                method="Basic Paragraph",
                chunk_count=0,
                chunks=[],
                processing_time=time.time() - start_time,
                total_size=0,
                avg_chunk_size=0,
                min_chunk_size=0,
                max_chunk_size=0,
                has_key_phrases=False,
                has_summaries=False,
                error=str(e)
            )
    
    def extract_enhanced_chunks(self, document_text: str, filename: str) -> ChunkingResult:
        """Extract chunks using OpenAI intelligent semantic chunking via Azure Function"""
        start_time = time.time()
        
        try:
            # Check if this is a PDF file that needs special handling
            is_pdf = filename.endswith('.pdf')
            
            if is_pdf and document_text == "PDF_PLACEHOLDER":
                # For PDF files, try to find the actual file and read it as binary
                file_path = None
                for root, dirs, files in os.walk('.'):
                    if filename in files:
                        file_path = os.path.join(root, filename)
                        break
                
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        import base64
                        file_content = f.read()
                        encoded_content = base64.b64encode(file_content).decode('utf-8')
                else:
                    # If we can't find the PDF, skip processing
                    return ChunkingResult(
                        chunks=[],
                        chunk_count=0,
                        total_chars=0,
                        processing_time=time.time() - start_time,
                        key_phrases=[],
                        summary="PDF file not found",
                        total_size=0,
                        avg_chunk_size=0,
                        min_chunk_size=0,
                        max_chunk_size=0,
                        has_key_phrases=False,
                        has_summaries=False,
                        error="PDF file not found"
                    )
            else:
                # For text files, create temporary file
                import tempfile
                import base64
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                    temp_file.write(document_text)
                    temp_file_path = temp_file.name
                
                # Read file content as binary
                with open(temp_file_path, 'rb') as file:
                    file_content = file.read()
                
                # Encode for Azure Function
                encoded_content = base64.b64encode(file_content).decode('utf-8')
                
                # Clean up temp file
                os.unlink(temp_file_path)
            
            # Prepare payload (use correct format for Azure Function)
            payload = {
                "file_content": encoded_content,
                "filename": filename
            }
            
            # Call Azure Function
            import requests
            response = requests.post(
                self.function_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract chunk details
                chunk_details = result.get('chunk_details', [])
                chunks = []
                total_size = 0
                
                for i, chunk_data in enumerate(chunk_details):
                    chunk_size = chunk_data.get('chunk_size', len(chunk_data.get('content', '')))
                    total_size += chunk_size
                    
                    chunk = {
                        'id': i + 1,
                        'title': chunk_data.get('ai_title', f"Enhanced Section {i + 1}"),
                        'content': chunk_data.get('content', ''),
                        'size': chunk_size,
                        'index': i,
                        'key_phrases': chunk_data.get('key_phrases', []),
                        'summary': chunk_data.get('summary', ''),
                        'ai_enhanced': True
                    }
                    chunks.append(chunk)
                
                return ChunkingResult(
                    method="OpenAI Intelligent Chunking",
                    chunk_count=len(chunks),
                    chunks=chunks,
                    processing_time=processing_time,
                    total_size=total_size,
                    avg_chunk_size=total_size / len(chunks) if chunks else 0,
                    min_chunk_size=min(c['size'] for c in chunks) if chunks else 0,
                    max_chunk_size=max(c['size'] for c in chunks) if chunks else 0,
                    has_key_phrases=len(chunks) > 0 and 'key_phrases' in chunks[0],
                    has_summaries=len(chunks) > 0 and 'summary' in chunks[0]
                )
            else:
                return ChunkingResult(
                    method="OpenAI Intelligent Chunking",
                    chunk_count=0,
                    chunks=[],
                    processing_time=processing_time,
                    total_size=0,
                    avg_chunk_size=0,
                    min_chunk_size=0,
                    max_chunk_size=0,
                    has_key_phrases=False,
                    has_summaries=False,
                    error=f"Azure Function error: {response.status_code} - {response.text}"
                )
                    
        except Exception as e:
            return ChunkingResult(
                method="OpenAI Enhanced",
                chunk_count=0,
                chunks=[],
                processing_time=time.time() - start_time,
                total_size=0,
                avg_chunk_size=0,
                min_chunk_size=0,
                max_chunk_size=0,
                has_key_phrases=False,
                has_summaries=False,
                error=str(e)
            )
    
    def analyze_size_distribution(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze chunk size distribution"""
        if not chunks:
            return {"error": "No chunks to analyze"}
        
        sizes = [chunk['size'] for chunk in chunks]
        
        return {
            "mean": statistics.mean(sizes),
            "median": statistics.median(sizes),
            "std_dev": statistics.stdev(sizes) if len(sizes) > 1 else 0,
            "min": min(sizes),
            "max": max(sizes),
            "range": max(sizes) - min(sizes),
            "quartiles": {
                "q1": sorted(sizes)[len(sizes)//4] if len(sizes) > 4 else min(sizes),
                "q3": sorted(sizes)[3*len(sizes)//4] if len(sizes) > 4 else max(sizes)
            }
        }
    
    def calculate_quality_score(self, basic_result: ChunkingResult, enhanced_result: ChunkingResult) -> float:
        """Calculate a quality score comparing the two methods"""
        score = 0.0
        
        # Size consistency (30% of score)
        if enhanced_result.chunk_count > 0 and basic_result.chunk_count > 0:
            if len(basic_result.chunks) > 1:
                basic_cv = statistics.stdev([c['size'] for c in basic_result.chunks]) / basic_result.avg_chunk_size
            else:
                basic_cv = 0  # Single chunk has perfect consistency
                
            if len(enhanced_result.chunks) > 1:
                enhanced_cv = statistics.stdev([c['size'] for c in enhanced_result.chunks]) / enhanced_result.avg_chunk_size
            else:
                enhanced_cv = 0  # Single chunk has perfect consistency
            
            # Lower coefficient of variation is better
            if basic_cv > enhanced_cv:
                score += 30
            elif enhanced_cv < basic_cv * 1.2:  # Similar consistency
                score += 20
        
        # Feature richness (40% of score)
        if enhanced_result.has_key_phrases:
            score += 20
        if enhanced_result.has_summaries:
            score += 20
        
        # Processing efficiency (30% of score) 
        if enhanced_result.processing_time > 0 and basic_result.processing_time > 0:
            if enhanced_result.processing_time < basic_result.processing_time * 3:  # Allow 3x processing time for enhanced features
                score += 30
            elif enhanced_result.processing_time < basic_result.processing_time * 5:
                score += 15
        elif enhanced_result.processing_time > 0:  # Basic was too fast to measure
            score += 15  # Give some credit for successful processing
        
        return min(score, 100.0)  # Cap at 100
    
    def generate_recommendations(self, comparison: ComparisonMetrics) -> List[str]:
        """Generate recommendations based on comparison results"""
        recommendations = []
        
        basic = comparison.basic_result
        enhanced = comparison.enhanced_result
        
        if enhanced.error:
            recommendations.append(f"🔧 Fix enhanced chunking error: {enhanced.error}")
            return recommendations
        
        # Chunk count comparison
        if enhanced.chunk_count > basic.chunk_count * 1.5:
            recommendations.append("⚠️ Enhanced chunking creates significantly more chunks - consider adjusting chunk size thresholds")
        elif enhanced.chunk_count < basic.chunk_count * 0.5:
            recommendations.append("⚠️ Enhanced chunking creates fewer chunks - may be missing content granularity")
        else:
            recommendations.append("✅ Chunk count is reasonable compared to basic method")
        
        # Size distribution
        if enhanced.avg_chunk_size > basic.avg_chunk_size * 2:
            recommendations.append("📏 Enhanced chunks are much larger - consider breaking down complex sections")
        elif enhanced.avg_chunk_size < basic.avg_chunk_size * 0.5:
            recommendations.append("📏 Enhanced chunks are much smaller - may be over-segmenting content")
        
        # Features
        if enhanced.has_key_phrases:
            recommendations.append("✨ Key phrase extraction adds valuable metadata")
        if enhanced.has_summaries:
            recommendations.append("✨ Summaries provide helpful content overview")
        
        # Performance
        if enhanced.processing_time > basic.processing_time * 10:
            recommendations.append("⏱️ Enhanced processing is significantly slower - consider optimization")
        
        # Quality score
        if comparison.quality_score >= 80:
            recommendations.append("🏆 Enhanced chunking shows excellent quality improvements")
        elif comparison.quality_score >= 60:
            recommendations.append("👍 Enhanced chunking shows good quality improvements")
        elif comparison.quality_score >= 40:
            recommendations.append("🤔 Enhanced chunking shows moderate improvements")
        else:
            recommendations.append("⚠️ Enhanced chunking may need tuning to show clear benefits")
        
        return recommendations
    
    def compare_chunking_methods(self, document_text: str, filename: str) -> ComparisonMetrics:
        """Compare basic vs enhanced chunking for a document"""
        
        if self.verbose:
            print(f"\n🔍 Analyzing document: {filename}")
            print("=" * 50)
        
        # Test basic chunking
        if self.verbose:
            print("📄 Testing basic paragraph chunking...")
        basic_result = self.extract_basic_chunks(document_text, filename)
        
        # Test enhanced chunking
        if self.verbose:
            print("🤖 Testing OpenAI enhanced chunking...")
        enhanced_result = self.extract_enhanced_chunks(document_text, filename)
        
        # Calculate metrics
        chunk_count_diff = enhanced_result.chunk_count - basic_result.chunk_count
        avg_size_diff = enhanced_result.avg_chunk_size - basic_result.avg_chunk_size
        
        # Analyze size distributions
        basic_dist = self.analyze_size_distribution(basic_result.chunks)
        enhanced_dist = self.analyze_size_distribution(enhanced_result.chunks)
        
        size_distribution_comparison = {
            "basic": basic_dist,
            "enhanced": enhanced_dist
        }
        
        # Calculate quality score
        quality_score = self.calculate_quality_score(basic_result, enhanced_result)
        
        # Create comparison
        comparison = ComparisonMetrics(
            document_name=filename,
            basic_result=basic_result,
            enhanced_result=enhanced_result,
            chunk_count_diff=chunk_count_diff,
            avg_size_diff=avg_size_diff,
            size_distribution_comparison=size_distribution_comparison,
            quality_score=quality_score,
            recommendations=[]
        )
        
        # Generate recommendations
        comparison.recommendations = self.generate_recommendations(comparison)
        
        return comparison
    
    def print_comparison_report(self, comparison: ComparisonMetrics):
        """Print a detailed comparison report"""
        print(f"\n📊 CHUNKING QUALITY COMPARISON REPORT")
        print("=" * 60)
        print(f"📄 Document: {comparison.document_name}")
        print(f"🎯 Quality Score: {comparison.quality_score:.1f}/100")
        
        # Basic results
        basic = comparison.basic_result
        print(f"\n📄 BASIC CHUNKING RESULTS:")
        print(f"   Method: {basic.method}")
        print(f"   Chunks: {basic.chunk_count}")
        print(f"   Avg Size: {basic.avg_chunk_size:.1f} chars")
        print(f"   Size Range: {basic.min_chunk_size} - {basic.max_chunk_size} chars")
        print(f"   Processing Time: {basic.processing_time:.2f}s")
        if basic.error:
            print(f"   ❌ Error: {basic.error}")
        
        # Enhanced results  
        enhanced = comparison.enhanced_result
        print(f"\n🤖 OPENAI INTELLIGENT CHUNKING RESULTS:")
        print(f"   Method: {enhanced.method}")
        print(f"   Chunks: {enhanced.chunk_count}")
        print(f"   Avg Size: {enhanced.avg_chunk_size:.1f} chars")
        print(f"   Size Range: {enhanced.min_chunk_size} - {enhanced.max_chunk_size} chars")
        print(f"   Processing Time: {enhanced.processing_time:.2f}s")
        print(f"   Key Phrases: {'✅ Yes' if enhanced.has_key_phrases else '❌ No'}")
        print(f"   Summaries: {'✅ Yes' if enhanced.has_summaries else '❌ No'}")
        if enhanced.error:
            print(f"   ❌ Error: {enhanced.error}")
        
        # Differences
        print(f"\n📈 COMPARISON:")
        print(f"   Chunk Count Difference: {comparison.chunk_count_diff:+d}")
        print(f"   Avg Size Difference: {comparison.avg_size_diff:+.1f} chars")
        print(f"   Processing Time Ratio: {enhanced.processing_time/basic.processing_time if basic.processing_time > 0 else 'N/A (basic too fast)'}x")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(comparison.recommendations, 1):
            print(f"   {i}. {rec}")
        
        # Sample chunks comparison
        print(f"\n📝 SAMPLE CHUNKS COMPARISON:")
        print("=" * 40)
        
        if basic.chunks and enhanced.chunks:
            print("🔹 Basic Chunk 1:")
            first_basic = basic.chunks[0]
            print(f"   Title: {first_basic['title']}")
            print(f"   Size: {first_basic['size']} chars")
            print(f"   Content: {first_basic['content'][:100]}{'...' if len(first_basic['content']) > 100 else ''}")
            
            print("\n🔹 OpenAI Intelligent Chunk 1:")
            first_enhanced = enhanced.chunks[0]
            print(f"   Title: {first_enhanced['title']}")
            print(f"   Size: {first_enhanced['size']} chars")
            print(f"   Content: {first_enhanced['content'][:100]}{'...' if len(first_enhanced['content']) > 100 else ''}")
            
            if 'key_phrases' in first_enhanced:
                print(f"   Key Phrases: {', '.join(first_enhanced['key_phrases'][:5])}")
            if 'summary' in first_enhanced:
                print(f"   Summary: {first_enhanced['summary'][:100]}{'...' if len(first_enhanced.get('summary', '')) > 100 else ''}")

def main():
    """Main entry point for chunking quality comparison"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Compare basic vs OpenAI enhanced document chunking quality"
    )
    parser.add_argument('--file', '-f', help='Specific file to test (default: use test documents)')
    parser.add_argument('--db-type', choices=['sqlite', 'azure_sql'], default='sqlite',
                       help='Database type for storage (default: sqlite)')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--save-report', help='Save detailed report to file')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = ChunkingQualityAnalyzer(verbose=args.verbose, db_type=args.db_type)
    
    # Test documents
    test_documents = []
    
    if args.file:
        # Use specific file
        if os.path.exists(args.file):
            filename = os.path.basename(args.file)
            if filename.endswith('.pdf'):
                # For PDF files, use placeholder content - Azure Function will handle PDF extraction
                content = "PDF_PLACEHOLDER"
                test_documents.append((filename, content))
            else:
                with open(args.file, 'r', encoding='utf-8') as f:
                    content = f.read()
                test_documents.append((filename, content))
        else:
            print(f"❌ File not found: {args.file}")
            return 1
    else:
        # Use standard test documents
        test_files = ['employee.pdf', 'sample_contract.txt', 'sample_employment.txt']
        
        for filename in test_files:
            filepath = os.path.join(os.path.dirname(__file__), filename)
            if os.path.exists(filepath):
                try:
                    if filename.endswith('.pdf'):
                        # For PDF files, we'll need to extract text first
                        print(f"📄 Found PDF: {filename} (will be processed by Azure Function)")
                        # Create a placeholder - the Azure Function will handle PDF extraction
                        content = "PDF_PLACEHOLDER"
                    else:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                    test_documents.append((filename, content))
                except Exception as e:
                    print(f"⚠️ Could not read {filename}: {e}")
    
    if not test_documents:
        print("❌ No test documents found. Place test files in the same directory or specify --file")
        return 1
    
    # Run comparisons
    all_comparisons = []
    
    for filename, content in test_documents:
        try:
            comparison = analyzer.compare_chunking_methods(content, filename)
            all_comparisons.append(comparison)
            analyzer.print_comparison_report(comparison)
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
    
    # Overall summary
    if len(all_comparisons) > 1:
        print(f"\n🏆 OVERALL SUMMARY")
        print("=" * 40)
        
        avg_quality = sum(c.quality_score for c in all_comparisons) / len(all_comparisons)
        print(f"Average Quality Score: {avg_quality:.1f}/100")
        
        enhanced_wins = sum(1 for c in all_comparisons if c.quality_score >= 60)
        print(f"Enhanced Method Success Rate: {enhanced_wins}/{len(all_comparisons)} ({enhanced_wins/len(all_comparisons)*100:.1f}%)")
    
    # Save report if requested
    if args.save_report:
        try:
            with open(args.save_report, 'w') as f:
                f.write(f"Chunking Quality Comparison Report\\n")
                f.write(f"Generated: {datetime.now()}\\n\\n")
                
                for comparison in all_comparisons:
                    f.write(f"Document: {comparison.document_name}\\n")
                    f.write(f"Quality Score: {comparison.quality_score:.1f}/100\\n")
                    f.write(f"Basic Chunks: {comparison.basic_result.chunk_count}\\n")
                    f.write(f"Enhanced Chunks: {comparison.enhanced_result.chunk_count}\\n")
                    f.write("\\n".join(comparison.recommendations))
                    f.write("\\n\\n")
            
            print(f"💾 Report saved to: {args.save_report}")
        except Exception as e:
            print(f"❌ Could not save report: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())