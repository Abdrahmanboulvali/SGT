import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:data_table_2/data_table_2.dart';
import 'package:http/http.dart' as http;

import 'LoginScreen.dart'; // فيه ApiConfig.baseUrl
import 'ticket_downloader.dart';
import 'ui/ui_widgets.dart';
import 'ui/app_theme.dart';

class MyReservationsScreen extends StatefulWidget {
  final int userId;
  const MyReservationsScreen({super.key, required this.userId});

  @override
  State<MyReservationsScreen> createState() => _MyReservationsScreenState();
}

class _MyReservationsScreenState extends State<MyReservationsScreen> {
  List allReservations = [];
  List filteredData = [];
  bool isLoading = true;

  final TextEditingController _searchController = TextEditingController();

  // =========================
  // ✅ Pagination (Slim)
  // =========================
  int _page = 1; // 1-based
  int _rowsPerPage = 5;

  int get _totalItems => filteredData.length;
  int get _totalPages {
    if (_rowsPerPage <= 0) return 1;
    final pages = (_totalItems / _rowsPerPage).ceil();
    return pages < 1 ? 1 : pages;
  }

  List get _pagedData {
    if (_totalItems == 0) return [];
    final start = (_page - 1) * _rowsPerPage;
    if (start >= _totalItems) return [];
    final end = (start + _rowsPerPage);
    return filteredData.sublist(start, end > _totalItems ? _totalItems : end);
  }

  void _clampPage() {
    final tp = _totalPages;
    if (_page < 1) _page = 1;
    if (_page > tp) _page = tp;
  }

  void _setPage(int newPage) {
    setState(() {
      _page = newPage;
      _clampPage();
    });
  }

  void _setRowsPerPage(int v) {
    setState(() {
      _rowsPerPage = v;
      _page = 1;
      _clampPage();
    });
  }

  Future<void> fetchData() async {
    setState(() => isLoading = true);

    final url = Uri.parse(
      "${ApiConfig.baseUrl}/api/mobile/mes-reservations/${widget.userId}/",
    );
    final response = await http.get(url);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);

      setState(() {
        allReservations = data;
        filteredData = allReservations;
        isLoading = false;

        _page = 1;
        _clampPage();
      });
    } else {
      setState(() => isLoading = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Erreur: ${response.statusCode}")),
      );
    }
  }

  @override
  void initState() {
    super.initState();
    fetchData();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _filterData(String query) {
    final q = query.toLowerCase().trim();
    setState(() {
      filteredData = allReservations.where((item) {
        final trajet = (item['trajet'] ?? "").toString().toLowerCase();
        return trajet.contains(q);
      }).toList();

      _page = 1;
      _clampPage();
    });
  }

  @override
  Widget build(BuildContext context) {
    return PageShell(
      maxWidth: 920,
      child: Column(
        children: [
          GradientHeader(
            title: "Mes réservations",
            subtitle: "Historique • Statut • Tickets PDF",
            icon: Icons.history,
          ),
          const SizedBox(height: 12),

          SoftCard(
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(
                      hintText: "Rechercher un trajet...",
                      prefixIcon: Icon(Icons.search),
                    ),
                    onChanged: _filterData,
                  ),
                ),
                const SizedBox(width: 10),
                IconButton(
                  tooltip: "Rafraîchir",
                  onPressed: fetchData,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          Expanded(
            child: isLoading
                ? const Center(child: CircularProgressIndicator())
                : LayoutBuilder(
                    builder: (context, c) {
                      final isSmall = c.maxWidth < 700;

                      if (filteredData.isEmpty) {
                        return const Center(
                          child: Text(
                            "Aucune réservation.",
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                        );
                      }

                      // ✅ Small: Cards + Slim pager
                      if (isSmall) {
                        final pageData = _pagedData;

                        return Column(
                          children: [
                            Expanded(
                              child: ListView.separated(
                                itemCount: pageData.length,
                                separatorBuilder: (_, __) =>
                                    const SizedBox(height: 10),
                                itemBuilder: (context, i) {
                                  final res = pageData[i];
                                  final statut = (res['statut'] ?? "").toString();
                                  final paiement =
                                      (res['statut_paiement'] ?? "").toString();
                                  final total = (res['prix_total'] ?? "").toString();

                                  final ticketUrl =
                                      (res['ticket_url'] ?? "").toString().trim();
                                  final canDownload = ticketUrl.isNotEmpty;

                                  return SoftCard(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          res['trajet'].toString(),
                                          style: const TextStyle(
                                            fontWeight: FontWeight.w900,
                                            fontSize: 16,
                                          ),
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          "Date: ${res['date']}",
                                          style: TextStyle(
                                            color: Colors.grey.shade700,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                        const SizedBox(height: 10),

                                        Wrap(
                                          spacing: 8,
                                          runSpacing: 8,
                                          children: [
                                            _buildStatusChip(statut),
                                            _buildPaymentChip(paiement),
                                            Chip(
                                              label: Text(
                                                "$total MRU",
                                                style: TextStyle(
                                                  color: AppTheme.primary,
                                                  fontWeight: FontWeight.w900,
                                                  fontSize: 12,
                                                ),
                                              ),
                                              backgroundColor:
                                                  AppTheme.primary.withOpacity(.10),
                                              side: BorderSide(
                                                color: AppTheme.primary.withOpacity(.35),
                                              ),
                                            ),
                                          ],
                                        ),

                                        const SizedBox(height: 12),

                                        SizedBox(
                                          width: double.infinity,
                                          child: ElevatedButton.icon(
                                            onPressed: canDownload
                                                ? () async {
                                                    try {
                                                      await TicketDownloader
                                                          .downloadAndOpenPdf(
                                                        context: context,
                                                        url: ticketUrl,
                                                        fileName:
                                                            "ticket_${res['id']}.pdf",
                                                      );
                                                    } catch (e) {
                                                      if (!mounted) return;
                                                      ScaffoldMessenger.of(context)
                                                          .showSnackBar(
                                                        SnackBar(
                                                          content: Text(
                                                              "Erreur téléchargement: $e"),
                                                        ),
                                                      );
                                                    }
                                                  }
                                                : null,
                                            icon: const Icon(Icons.picture_as_pdf),
                                            label: Text(canDownload
                                                ? "Télécharger le ticket"
                                                : "En attente"),
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                },
                              ),
                            ),
                            const SizedBox(height: 10),
                            _buildSlimPager(),
                          ],
                        );
                      }

                      // ✅ Large: DataTable2 + Slim pager
                      final pageData = _pagedData;

                      return Column(
                        children: [
                          Expanded(
                            child: SoftCard(
                              child: DataTable2(
                                columnSpacing: 12,
                                horizontalMargin: 12,
                                minWidth: 680,
                                headingRowHeight: 44,
                                columns: const [
                                  DataColumn2(
                                      label: Text("Trajet"), size: ColumnSize.L),
                                  DataColumn(label: Text("Date")),
                                  DataColumn(label: Text("Statut")),
                                  DataColumn(label: Text("Paiement")),
                                  DataColumn(label: Text("Total")),
                                  DataColumn(label: Text("Ticket")),
                                ],
                                rows: pageData.map((res) {
                                  final statut = (res['statut'] ?? "").toString();
                                  final paiement =
                                      (res['statut_paiement'] ?? "").toString();
                                  final total = (res['prix_total'] ?? "").toString();

                                  final ticketUrl =
                                      (res['ticket_url'] ?? "").toString().trim();
                                  final canDownload = ticketUrl.isNotEmpty;

                                  return DataRow(cells: [
                                    DataCell(Text(res['trajet'].toString())),
                                    DataCell(Text(res['date'].toString())),
                                    DataCell(_buildStatusChip(statut)),
                                    DataCell(_buildPaymentChip(paiement)),
                                    DataCell(Text("$total MRU")),
                                    DataCell(
                                      ElevatedButton.icon(
                                        onPressed: canDownload
                                            ? () async {
                                                try {
                                                  await TicketDownloader
                                                      .downloadAndOpenPdf(
                                                    context: context,
                                                    url: ticketUrl,
                                                    fileName:
                                                        "ticket_${res['id']}.pdf",
                                                  );
                                                } catch (e) {
                                                  if (!mounted) return;
                                                  ScaffoldMessenger.of(context)
                                                      .showSnackBar(
                                                    SnackBar(
                                                      content: Text(
                                                          "Erreur téléchargement: $e"),
                                                    ),
                                                  );
                                                }
                                              }
                                            : null,
                                        icon: const Icon(Icons.picture_as_pdf),
                                        label: Text(
                                            canDownload ? "Télécharger" : "En attente"),
                                      ),
                                    ),
                                  ]);
                                }).toList(),
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          _buildSlimPager(),
                        ],
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  // =========================
  // ✅ Slim Pager Widget
  // =========================
  Widget _buildSlimPager() {
    _clampPage();

    final canPrev = _page > 1;
    final canNext = _page < _totalPages;

    Widget smallBtn({
      required IconData icon,
      required VoidCallback? onTap,
      String? tooltip,
    }) {
      return IconButton(
        tooltip: tooltip,
        onPressed: onTap,
        icon: Icon(icon, size: 18),
        padding: EdgeInsets.zero,
        constraints: const BoxConstraints.tightFor(width: 34, height: 34),
        splashRadius: 18,
      );
    }

    final pageSizeItems = const [5, 10, 20];

    return Align(
      alignment: Alignment.center,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: Colors.grey.shade200),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 16,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                "Page $_page/$_totalPages",
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              const SizedBox(width: 10),

              Text(
                "• $_totalItems élément(s)",
                style: TextStyle(
                  color: Colors.grey.shade700,
                  fontWeight: FontWeight.w700,
                  fontSize: 12,
                ),
              ),
              const SizedBox(width: 12),

              // first / prev
              smallBtn(
                icon: Icons.first_page_rounded,
                tooltip: "Première",
                onTap: canPrev ? () => _setPage(1) : null,
              ),
              smallBtn(
                icon: Icons.chevron_left_rounded,
                tooltip: "Précédent",
                onTap: canPrev ? () => _setPage(_page - 1) : null,
              ),

              // current page pill (thin)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 6),
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withOpacity(.10),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: AppTheme.primary.withOpacity(.25)),
                ),
                child: Text(
                  "$_page",
                  style: TextStyle(
                    color: AppTheme.primary,
                    fontWeight: FontWeight.w900,
                    fontSize: 12,
                  ),
                ),
              ),

              // next / last
              smallBtn(
                icon: Icons.chevron_right_rounded,
                tooltip: "Suivant",
                onTap: canNext ? () => _setPage(_page + 1) : null,
              ),
              smallBtn(
                icon: Icons.last_page_rounded,
                tooltip: "Dernière",
                onTap: canNext ? () => _setPage(_totalPages) : null,
              ),

              const SizedBox(width: 12),

              Text(
                "Par page:",
                style: TextStyle(
                  color: Colors.grey.shade700,
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                ),
              ),
              const SizedBox(width: 6),

              // page size dropdown (small)
              DropdownButtonHideUnderline(
                child: SizedBox(
                  height: 30,
                  child: DropdownButton<int>(
                    value: _rowsPerPage,
                    items: pageSizeItems
                        .map((v) => DropdownMenuItem<int>(
                              value: v,
                              child: Text(
                                v.toString(),
                                style: const TextStyle(
                                  fontWeight: FontWeight.w900,
                                  fontSize: 12,
                                ),
                              ),
                            ))
                        .toList(),
                    onChanged: (v) {
                      if (v == null) return;
                      _setRowsPerPage(v);
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // =========================
  // ✅ Chips
  // =========================
  Widget _buildStatusChip(String status) {
    final s = status.toLowerCase();
    final isConfirmed = s.contains('confirm');
    final isCanceled = s.contains('annul');

    Color color;
    if (isCanceled) {
      color = Colors.red;
    } else if (isConfirmed) {
      color = Colors.green;
    } else {
      color = Colors.orange;
    }

    return Chip(
      label: Text(
        status,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
      backgroundColor: color.withOpacity(0.10),
      side: BorderSide(color: color.withOpacity(.45)),
    );
  }

  Widget _buildPaymentChip(String payment) {
    final p = payment.toLowerCase();
    final isPaid = p.contains("paye") || p.contains("payé");

    final color = isPaid ? Colors.green : Colors.orange;

    return Chip(
      label: Text(
        payment,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
      backgroundColor: color.withOpacity(0.10),
      side: BorderSide(color: color.withOpacity(.45)),
    );
  }
}
