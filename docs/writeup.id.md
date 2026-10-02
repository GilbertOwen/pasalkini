# Mengapa RAG mengutip aturan yang sudah tidak berlaku, dan apa yang diperlukan untuk menghentikannya

*Draf, 2 Oktober 2026. Belum dipublikasikan. Semua angka berasal dari `docs/eval-results.md`; kunci jawaban di baliknya masih draf buatan AI yang belum diperiksa oleh manusia.*

## Masalahnya

Berapa lama perjanjian kerja waktu tertentu (PKWT) boleh berlangsung? Jawaban yang benar bergantung pada tanggal yang dimaksud:

- Juni 2019: dua tahun, dapat diperpanjang satu kali untuk satu tahun (UU 13/2003 Pasal 59);
- Juni 2022: lima tahun secara keseluruhan (PP 35/2021 Pasal 8);
- Juni 2025: lima tahun secara keseluruhan, kini berdasarkan Putusan MK 168/PUU-XXI/2023.

Hukum ketenagakerjaan Indonesia sudah beberapa kali berubah sejak 2020 (UU 11/2020, Perppu 2/2022, UU 6/2023, putusan Mahkamah Konstitusi tahun 2024), dan undang-undang ketenagakerjaan yang baru sedang dibahas di DPR. Semua teks itu mengatur hal yang sama dengan kata-kata yang hampir sama. Sistem *retrieval* mengurutkan teks berdasarkan kemiripan, sehingga bunyi tahun 2003, 2020 dan 2022 dari pasal yang sama mendapat nilai yang sama. Bunyi mana yang sampai ke model nyaris kebetulan. Model lalu menjawab dengan yakin, lengkap dengan kutipan pasal yang memang ada.

PasalKini adalah asisten kecil yang menjawab pertanyaan hukum ketenagakerjaan **untuk suatu tanggal**. Ia berjalan di GPU laptop (6 GB) dengan model 4B. Berikut pelajaran dari membangunnya.

## 1. Ukur dulu

78 pertanyaan, masing-masing dengan tanggal, sumber yang menjadi dasar jawaban yang benar, dan sumber yang tidak boleh dikutip. Separuhnya berpasangan: pertanyaan yang sama untuk dua atau tiga tanggal.

| Cara kerja | Jawaban mengutip aturan yang tidak berlaku pada tanggal itu |
|---|---|
| RAG biasa | 65% (37 dari 57) |
| Setiap potongan teks diberi label masa berlakunya, tanpa penyaringan | 65% (37 dari 57) |
| Hanya versi yang berlaku pada tanggal itu yang dicari | 0% |

Ada dua hal di tabel itu. RAG biasa mengutip aturan lama pada dua dari tiga jawaban. Dan **memberi tahu model tanggalnya tidak mengubah apa-apa**: dengan tulisan "berlaku 25 Maret 2003 s.d. 1 November 2020" pada setiap potongan, angkanya tetap 65%, dan model malah lebih sering mengarang ID sumber. Yang berhasil adalah tidak memberikan teks itu kepadanya.

## 2. Modelkan waktu, lalu saring sebelum mencari

Hukum berubah lewat peristiwa: pasal diubah, disisipkan atau dihapus; putusan pengadilan memberi syarat; undang-undang dicabut dan bunyi sebelumnya berlaku lagi. PasalKini mengambil peristiwa itu dari undang-undang perubahannya sendiri, lalu memutarnya ulang menurut urutan tanggal. Hasilnya: semua versi setiap pasal, masing-masing dengan masa berlakunya. Ada 809 versi dari 12 peraturan dan putusan.

Sebuah pertanyaan kemudian hanya dicarikan di antara versi yang berlaku pada tanggalnya. Versi yang tidak berlaku tidak bisa ditemukan, jadi tidak bisa dikutip. Itulah intinya, dan itu bukan *prompt*.

## 3. Mengutip sumber yang benar belum berarti menjawab dengan benar

Dengan saringan tanggal dan pemeriksaan bahwa setiap kutipan memang ada di sumbernya, sistem mengutip sumber yang diharapkan pada 89% pertanyaan pengembangan. Setelah 42 jawabannya dibaca dan dibandingkan dengan kunci, **hanya 55% yang sepenuhnya benar**. Kesalahannya ada tepat di samping kutipan yang benar: nama peraturan yang salah, tanggal perubahan yang salah, "dua kali upah pokok" padahal "dua kali ketentuan", kalimat yang salah dibaca.

Dua perubahan menaikkannya menjadi 33–36 dari 42:

- **Pilih kutipan dulu, baru jawab hanya dari kutipan itu.** Satu panggilan memilih kutipan, program memeriksanya, panggilan kedua menulis satu sampai tiga kalimat hanya dari kutipan tersebut, dimulai dari kata-kata yang menjadi dasarnya.
- **Yang bisa dinyatakan program tidak ditulis oleh model.** Apakah suatu pasal masih berlaku dan sejak kapan, besar pesangon, apa yang diubah putusan MK: semuanya berasal dari model waktu atau kalkulator. Setelah hitungan, kalimat model tentang jumlah uang tidak ditampilkan sama sekali. Kalimat itu salah di empat percobaan dengan empat cara berbeda, dan tidak ada *prompt* yang memperbaikinya.

## 4. Kumpulan soal sendiri terlalu memuji

Pada pertanyaan yang tidak pernah dipakai untuk menyetel sistem, dinilai oleh juri otomatis, hasilnya 24 dari 36. Lalu aplikasinya dijalankan, dan pertanyaan yang diketik sendiri hasilnya lebih buruk lagi: dengan "kontrak kerja waktu tertentu" sebagai ganti "PKWT", sistem menjawab bahwa tidak ada batas maksimal.

Maka setiap pertanyaan diberi satu rumusan lain, dan diukur terpisah. Dengan rumusan lain, jawaban benar pada pertanyaan pengembangan turun dari 36 menjadi 26 dari 42. Setelah enam perubahan, angkanya 34. Pada separuh yang disimpan (tidak pernah dilihat satu per satu), kenaikannya 22 menjadi 25 dari 36: nyata, tetapi kecil. Angka kedua itulah yang patut dipercaya.

## 5. Jaminan yang bergantung pada model bukanlah jaminan

Pertanyaan dengan rumusan lain menemukan hal yang lebih serius daripada jawaban salah. Dua jawaban pada separuh yang disimpan mengutip bunyi yang sudah tidak berlaku: pertama kalinya sejak saringan tanggal dipasang.

Tanggalnya benar. Tetapi pertanyaan tentang *status* pasal ("apakah Pasal 59 masih berlaku?") dicarikan di semua bunyi sampai tanggal itu, karena jawabannya memerlukan bunyi lama, dan **model yang menentukan pertanyaan mana yang termasuk pertanyaan status**. Tiga pertanyaan biasa dianggapnya pertanyaan status, dan bunyi lama pun sampai ke jawaban. Saringannya dibuat oleh program. Pilihan saringannya tidak.

Perbaikannya adalah aturan di dalam program: hanya bunyi yang berlaku pada tanggal itu yang boleh menjadi sumber, apa pun anggapan model tentang jenis pertanyaannya. Bunyi yang lebih lama ditampilkan terpisah, sebagai bunyi sebelumnya. Sekarang juga ada uji yang sengaja memaksakan kesalahan itu: setiap pertanyaan biasa dijalankan dengan jenis yang keliru. Sebelumnya, 7 dari 60 jawaban seperti itu mengutip aturan lama. Sesudahnya, tidak ada.

Tidak satu pun pertanyaan uji yang biasa pernah melewati jalur itu. Perlu pertanyaan dengan rumusan lain, dari separuh yang disimpan, untuk menemukannya, dan kesalahan yang disengaja untuk membuktikan bahwa celahnya sudah tertutup.

## Yang tidak berhasil

- **Mode berpikir** pada model dan GPU ini: 1 dari 36 jawaban selesai dalam batas token, masing-masing 37 detik.
- **Agen** yang memilih pencariannya sendiri: mengutip sumber yang diharapkan pada 82%, sedangkan alur tetap 91%, dan lebih lambat.
- **Menulis ulang pertanyaan dengan model** sebelum pencarian: tidak ada kenaikan.
- **Menahan jawaban berbentuk "tidak ada aturannya"**: dua jawaban menjadi lebih buruk dan tidak ada yang membaik. Bertanya ulang dengan bunyi pasal selengkapnya ternyata berhasil.

## Keterbatasan

- Belum ada manusia yang memeriksa kunci jawaban atau menilai jawaban. Kunci, pembacaan dan juri semuanya pekerjaan AI.
- 78 pertanyaan itu sedikit; satu pertanyaan bernilai satu sampai tiga poin persentase.
- Model 4B masih bisa salah membaca kutipan yang ada di depannya. Dua jawaban pengembangan salah dengan cara itu di setiap percobaan.
- Aturan yang sudah dihapus tidak ditemukan oleh pertanyaan yang tidak menyebut pasalnya.
- Undang-undang ketenagakerjaan yang baru belum ada di dalam korpus.

## Pelajaran

1. Untuk hukum, mirip belum tentu berlaku. Modelkan waktu secara eksplisit dan saring sebelum mengurutkan.
2. Hitung kutipan usang dan jawaban benar secara terpisah. Sistem bisa mengutip pasal yang tepat dan tetap salah.
3. Kurangi pekerjaan model. Setiap kalimat yang bisa ditulis program adalah kalimat yang tidak lagi salah.
4. Rumuskan ulang pertanyaan uji Anda. Lalu simpan separuhnya, dan percayai separuh itu.
5. Jika sebuah jaminan melewati penilaian model, ujilah dengan model yang sengaja dibuat salah.

PasalKini memberikan informasi hukum, bukan nasihat hukum. Kode: `github.com/GilbertOwen/pasalkini` (untuk saat ini privat).
