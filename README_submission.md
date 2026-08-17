# Báo cáo Thực hành Lab 17 — Multi-Memory Agent với Zep

**Học viên:** Tô Minh Đức | **Mã HV:** 2A202601043  
**Kết quả:** **11/11 PASS (100%)** trên Practice; No-Memory: **2/11 PASS (18.2%)**.

---

## 1. Ba câu hỏi cốt lõi

### Câu 1: Layer quan trọng nhất & Minh chứng
**Long-term Memory** quan trọng nhất (**20/56đ auto** với 4 cases: **E02, E03, E08, E09**). Layer này giải quyết bài toán cốt lõi của agent đa phiên:
- **E02/E03**: Giữ preference (`Python`) và open-loop tasks (`benchmark report`, `16:00`) qua thread mới.
- **E08 (Recency/Conflict)**: Ưu tiên fact mới (`BLUEBIRD-42` $\rightarrow$ `TypeScript`/`NestJS`) đè preference cũ (`ORCHID-27` $\rightarrow$ `Python`).
- **E09 (User Isolation)**: Cách ly tuyệt đối giữa `lan-lab17` (`LOTUS-88`, `Java`/`Spring Boot`) và `minh-lab17`, chống rò rỉ dữ liệu.

### Câu 2: Trade-off Zep Context Block vs. Redis + Qdrant
- **Zep V3 (Managed)**: Tự động trích xuất Knowledge Graph, dynamic relevance assembly theo thread slice, hỗ trợ namespace isolation & Right-to-be-Forgotten. *Nhược điểm:* Độ trễ cloud (~1-2s), opaque pipeline, chi phí API.
- **Redis + Qdrant (Self-managed)**: Độ trễ cực thấp (<5ms), kiểm soát dữ liệu on-premise, chi phí cố định. *Nhược điểm:* Phải tự code logic trích xuất entity, graph traversal, conflict resolution và compaction.

### Câu 3: Guardrail chống Memory Poisoning
1. **Provenance Tracking**: Ghi kèm `source_id`, `timestamp`, `confidence` cho mọi durable write.
2. **Quyền hạn Heartbeat**: Background tasks chỉ dọn dẹp/đánh dấu stale, **tuyệt đối không tự cấp quyền hay ghi instruction mới** (`control_plane/AGENTS.md`).
3. **Policy-Protected Layer**: Rules an toàn luôn được bảo vệ, không bị token compaction cắt bỏ.
4. **Consent Gate**: Kiểm tra opt-in (`consent.json`) và sanitize PII/injection trước khi lưu trữ.

---

## 2. Phân tích Benchmark & Compaction

1. **Layer yếu nhất**: Ở No-Memory, **Long-term, Episodic và Semantic đều 0%**. Với Student Memory, tất cả layer đạt **100%**.
2. **Query tốn token nhất**: **E07** (Mixed, ~380 tokens) và **E08** do ghép nhiều layer và fact edges.
3. **Case Mixed E07**: Kết hợp **Long-Term** (preference `Python`) + **Semantic** (Domain rule `Idempotency-Key`). Thiếu 1 trong 2 sẽ sinh sai code.
4. **Token Reduction vs. Hit Rate**: Student Memory giảm **14.2%** token nhờ budget 10/4/3/3. No-Memory giảm **81.8%** nhưng hit rate chỉ **18.2%** vì mất toàn bộ context.
5. **E10 Compaction**: Sliding window co 16 turns còn 6 turns gần nhất nhưng bảo tồn `REVIEW-DEADLINE-1600` nhờ **Durable Notes**.

