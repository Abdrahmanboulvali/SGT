import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:data_table_2/data_table_2.dart';
import 'package:http/http.dart' as http;

import 'LoginScreen.dart';
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

  Future<void> fetchData() async {
    setState(() => isLoading = true);

    final url = Uri.parse("${ApiConfig.baseUrl}/api/mobile/mes-reservations/${widget.userId}/");
    final response = await http.get(url);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      setState(() {
        allReservations = data;
        filteredData = allReservations;
        isLoading = false;
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

  void _filterData(String query) {
    setState(() {
      filteredData = allReservations
          .where((item) => item['trajet']
              .toString()
              .toLowerCase()
              .contains(query.toLowerCase()))
          .toList();
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

                      // ✅ Small: Cards
                      if (isSmall) {
                        return ListView.separated(
                          itemCount: filteredData.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 10),
                          itemBuilder: (context, i) {
                            final res = filteredData[i];
                            final statut = (res['statut'] ?? "").toString();
                            final paiement = (res['statut_paiement'] ?? "").toString();
                            final total = (res['prix_total'] ?? "").toString();
                            final ticketUrl = (res['ticket_url'] ?? "").toString().trim();
                            final canDownload = ticketUrl.isNotEmpty;

                            return SoftCard(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    res['trajet'].toString(),
                                    style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    "Date: ${res['date']}",
                                    style: TextStyle(color: Colors.grey.shade700, fontWeight: FontWeight.w600),
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
                                        backgroundColor: AppTheme.primary.withOpacity(.10),
                                        side: BorderSide(color: AppTheme.primary.withOpacity(.35)),
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
                                                await TicketDownloader.downloadAndOpenPdf(
                                                  context: context,
                                                  url: ticketUrl,
                                                  fileName: "ticket_${res['id']}.pdf",
                                                );
                                              } catch (e) {
                                                if (!mounted) return;
                                                ScaffoldMessenger.of(context).showSnackBar(
                                                  SnackBar(content: Text("Erreur téléchargement: $e")),
                                                );
                                              }
                                            }
                                          : null,
                                      icon: const Icon(Icons.picture_as_pdf),
                                      label: Text(canDownload ? "Télécharger le ticket" : "En attente"),
                                    ),
                                  ),
                                ],
                              ),
                            );
                          },
                        );
                      }

                      // ✅ Large: DataTable2 (نفس جدولك)
                      return SoftCard(
                        child: DataTable2(
                          columnSpacing: 12,
                          horizontalMargin: 12,
                          minWidth: 680,
                          headingRowHeight: 44,
                          columns: const [
                            DataColumn2(label: Text("Trajet"), size: ColumnSize.L),
                            DataColumn(label: Text("Date")),
                            DataColumn(label: Text("Statut")),
                            DataColumn(label: Text("Paiement")),
                            DataColumn(label: Text("Total")),
                            DataColumn(label: Text("Ticket")),
                          ],
                          rows: filteredData.map((res) {
                            final statut = (res['statut'] ?? "").toString();
                            final paiement = (res['statut_paiement'] ?? "").toString();
                            final total = (res['prix_total'] ?? "").toString();

                            final ticketUrl = (res['ticket_url'] ?? "").toString().trim();
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
                                            await TicketDownloader.downloadAndOpenPdf(
                                              context: context,
                                              url: ticketUrl,
                                              fileName: "ticket_${res['id']}.pdf",
                                            );
                                          } catch (e) {
                                            if (!mounted) return;
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(content: Text("Erreur téléchargement: $e")),
                                            );
                                          }
                                        }
                                      : null,
                                  icon: const Icon(Icons.picture_as_pdf),
                                  label: Text(canDownload ? "Télécharger" : "En attente"),
                                ),
                              ),
                            ]);
                          }).toList(),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

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
      label: Text(status, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w900)),
      backgroundColor: color.withOpacity(0.10),
      side: BorderSide(color: color.withOpacity(.45)),
    );
  }

  Widget _buildPaymentChip(String payment) {
    final p = payment.toLowerCase();
    final isPaid = p.contains("paye") || p.contains("payé");

    final color = isPaid ? Colors.green : Colors.orange;

    return Chip(
      label: Text(payment, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w900)),
      backgroundColor: color.withOpacity(0.10),
      side: BorderSide(color: color.withOpacity(.45)),
    );
  }
}
