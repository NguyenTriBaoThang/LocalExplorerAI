# Một SDK openai, dev bằng Gemini, demo bằng OpenAI

Nhóm phát triển bằng Gemini (tiết kiệm) nhưng demo bằng OpenAI (có sẵn credit). Toàn bộ lời gọi LLM đi qua SDK `openai`; Gemini được gọi qua endpoint tương thích OpenAI, nên đổi provider chỉ là đổi biến môi trường base URL / key / model. STT và TTS luôn dùng OpenAI vì lớp tương thích của Gemini không hỗ trợ.

## Consequences

Hai model phản ứng khác nhau với cùng prompt và tool. Một bộ prompt mẫu (golden set) phải chạy trên cả hai provider, và hai tuần cuối chạy hoàn toàn trên OpenAI. Embedding của Place tạo một lần bằng một provider cố định để vector không bị lẫn.
